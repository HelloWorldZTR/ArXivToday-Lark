"""Paper fetching, filtering, and local history persistence."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

import arxiv

from .models import Paper


def fetch_latest_papers(category: str, max_results: int = 100) -> list[Paper]:
    client = arxiv.Client()
    search = arxiv.Search(
        query=f"cat:{category}",
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
    )

    papers: list[Paper] = []
    for result in client.results(search):
        paper_id = result.get_short_id().split("v", maxsplit=1)[0]
        papers.append(
            {
                "title": result.title,
                "id": paper_id,
                "abstract": result.summary.replace("\n", " "),
                "url": result.entry_id,
                "published": result.published.date().isoformat(),
            }
        )
    return papers


def deduplicate_by_id(papers: Iterable[Paper]) -> list[Paper]:
    seen: set[str] = set()
    result: list[Paper] = []
    for paper in papers:
        if paper["id"] not in seen:
            seen.add(paper["id"])
            result.append(paper)
    return result


def filter_by_keywords(papers: Iterable[Paper], keywords: Iterable[str]) -> list[Paper]:
    keyword_set = {keyword.lower() for keyword in keywords}
    return [
        paper
        for paper in papers
        if keyword_set & set(paper["abstract"].lower().split())
    ]


class PaperHistory:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def exclude_seen(self, papers: Iterable[Paper]) -> list[Paper]:
        seen_ids = {paper["id"] for paper in self._read()}
        return [paper for paper in papers if paper["id"] not in seen_ids]

    def prepend(self, papers: Iterable[Paper]) -> None:
        new_papers = list(papers)
        existing = self._read()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(
                new_papers + existing,
                file,
                indent=4,
                ensure_ascii=False,
            )

    def _read(self) -> list[Paper]:
        if not self.path.exists():
            return []
        content = self.path.read_text(encoding="utf-8")
        if not content.strip():
            return []
        data = json.loads(content)
        if not isinstance(data, list):
            raise TypeError(f"Paper history must contain a list: {self.path}")
        return data
