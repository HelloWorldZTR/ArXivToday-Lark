"""Paper fetching and seen-paper persistence."""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from collections.abc import Iterable
from pathlib import Path

import arxiv

from .models import Paper

ARXIV_RETRY_DELAYS_SECONDS = (15.0, 30.0, 60.0, 120.0)


def fetch_latest_papers(category: str, max_results: int = 100) -> list[Paper]:
    search = arxiv.Search(
        query=f"cat:{category}",
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
    )

    return [_paper_from_result(result) for result in _results_with_backoff(search)]


def fetch_paper_by_id(paper_id: str) -> Paper:
    """Fetch one arXiv paper, preserving its current version for caching."""
    search = arxiv.Search(id_list=[paper_id], max_results=1)
    result = next(iter(_results_with_backoff(search)), None)
    if result is None:
        raise LookupError(f"arXiv paper not found: {paper_id}")
    return _paper_from_result(result)


def _results_with_backoff(search: arxiv.Search) -> list[object]:
    """Fetch one search, retrying rate limits and server errors exponentially."""
    for attempt in range(len(ARXIV_RETRY_DELAYS_SECONDS) + 1):
        try:
            # Disable the dependency's fixed-delay retries so all retries use
            # the explicit exponential schedule below.
            return list(arxiv.Client(num_retries=0).results(search))
        except arxiv.HTTPError as error:
            retryable = error.status == 429 or 500 <= error.status < 600
            if not retryable or attempt == len(ARXIV_RETRY_DELAYS_SECONDS):
                raise
            delay = ARXIV_RETRY_DELAYS_SECONDS[attempt]
            print(
                f"arXiv API returned HTTP {error.status}; "
                f"retrying in {delay:g}s"
            )
            time.sleep(delay)
    raise AssertionError("unreachable")


def _paper_from_result(result: object) -> Paper:
    short_id = result.get_short_id()  # type: ignore[attr-defined]
    paper_id = re.sub(r"v\d+$", "", short_id)
    return {
        "title": result.title,  # type: ignore[attr-defined]
        "id": paper_id,
        "abstract": result.summary.replace("\n", " "),  # type: ignore[attr-defined]
        "authors": tuple(str(author) for author in result.authors),  # type: ignore[attr-defined]
        "url": result.entry_id,  # type: ignore[attr-defined]
        "published": result.published.date().isoformat(),  # type: ignore[attr-defined]
        "version": short_id,
    }


def deduplicate_by_id(papers: Iterable[Paper]) -> list[Paper]:
    seen: set[str] = set()
    result: list[Paper] = []
    for paper in papers:
        if paper["id"] not in seen:
            seen.add(paper["id"])
            result.append(paper)
    return result


class SeenPaperStore:
    """Stores processed IDs and imports IDs from the legacy paper archive."""

    def __init__(
        self,
        path: str | Path,
        *,
        legacy_history_path: str | Path | None = None,
    ):
        self.path = Path(path)
        self.legacy_history_path = (
            Path(legacy_history_path) if legacy_history_path is not None else None
        )

    def exclude_seen(self, papers: Iterable[Paper]) -> list[Paper]:
        seen_ids = self.read_ids()
        return [paper for paper in papers if paper["id"] not in seen_ids]

    def commit(self, paper_ids: Iterable[str]) -> None:
        seen_ids = self.read_ids()
        seen_ids.update(paper_ids)
        baseline_date = self.baseline_date
        if baseline_date is None:
            raise RuntimeError("Seen-paper store must be initialized before commit")
        self._write_state(baseline_date, seen_ids)

    def initialize(self, baseline_date: str) -> None:
        """Create the first-run date baseline without processing old papers."""
        self._write_state(baseline_date, self.read_ids())

    @property
    def baseline_date(self) -> str | None:
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8") or "{}")
            if isinstance(data, dict):
                baseline = data.get("baseline_date")
                if isinstance(baseline, str):
                    return baseline
        return self._legacy_baseline_date()

    @property
    def is_initialized(self) -> bool:
        return self.baseline_date is not None

    def _write_state(self, baseline_date: str, seen_ids: set[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=self.path.parent,
            prefix=f".{self.path.name}.",
            delete=False,
        ) as file:
            json.dump(
                {
                    "baseline_date": baseline_date,
                    "seen_ids": sorted(seen_ids),
                },
                file,
                indent=2,
                ensure_ascii=False,
            )
            temporary_path = Path(file.name)
        os.replace(temporary_path, self.path)

    def read_ids(self) -> set[str]:
        seen_ids: set[str] = set()
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8") or "{}")
            stored_ids = data.get("seen_ids", []) if isinstance(data, dict) else data
            if not isinstance(stored_ids, list) or not all(
                isinstance(item, str) for item in stored_ids
            ):
                raise TypeError(f"Seen-paper state contains invalid IDs: {self.path}")
            seen_ids.update(stored_ids)
        seen_ids.update(self._read_legacy_ids())
        return seen_ids

    def _read_legacy_ids(self) -> set[str]:
        if self.legacy_history_path is None or not self.legacy_history_path.exists():
            return set()
        content = self.legacy_history_path.read_text(encoding="utf-8")
        if not content.strip():
            return set()
        data = json.loads(content)
        if not isinstance(data, list):
            raise TypeError(
                f"Legacy paper history must contain a list: {self.legacy_history_path}"
            )
        return {
            item["id"]
            for item in data
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }

    def _legacy_baseline_date(self) -> str | None:
        if self.legacy_history_path is None or not self.legacy_history_path.exists():
            return None
        content = self.legacy_history_path.read_text(encoding="utf-8")
        if not content.strip():
            return None
        data = json.loads(content)
        if not isinstance(data, list):
            return None
        published_dates = [
            item["published"]
            for item in data
            if isinstance(item, dict) and isinstance(item.get("published"), str)
        ]
        return max(published_dates, default=None)
