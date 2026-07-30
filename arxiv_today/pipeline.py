"""The complete paper collection and delivery pipeline."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from .config import AppConfig
from .lark import LarkPublisher, LarkPublishError
from .llm import LLMService
from .models import EvaluatedPaper, Paper, PaperReading, QualityAssessment
from .papers import SeenPaperStore, deduplicate_by_id, fetch_latest_papers
from .reading import PaperTextExtractor

PaperFetcher = Callable[[str, int], list[Paper]]


class LLMOperations(Protocol):
    def matches(self, paper: Paper, criteria: str) -> bool: ...

    def assess_quality(
        self, paper: Paper, *, threshold: int
    ) -> QualityAssessment | None: ...

    def create_reading(
        self,
        paper: Paper,
        *,
        full_text: str | None,
        chunk_characters: int,
    ) -> PaperReading: ...


class PublisherOperations(Protocol):
    def publish_digest(self, tag: str, papers: list[EvaluatedPaper]) -> None: ...

    def publish_reading(
        self, evaluated: EvaluatedPaper, reading: PaperReading
    ) -> None: ...


class TextExtractor(Protocol):
    def extract(self, paper: Paper) -> str | None: ...


class PaperPipeline:
    """Coordinates the one-shot fetch, evaluate, publish, and read workflow."""

    def __init__(
        self,
        config: AppConfig,
        *,
        fetcher: PaperFetcher = fetch_latest_papers,
        llm: LLMOperations | None = None,
        publisher: PublisherOperations | None = None,
        seen_store: SeenPaperStore | None = None,
        text_extractor: TextExtractor | None = None,
    ):
        self.config = config
        self.fetcher = fetcher
        self.llm = llm or LLMService(config.llm)
        self.publisher = publisher or LarkPublisher(config.lark)
        self.seen_store = seen_store or SeenPaperStore(
            config.seen_path,
            legacy_history_path=config.history_path,
        )
        self.text_extractor = text_extractor or PaperTextExtractor(
            config.reading.pdf_timeout_seconds
        )

    def run(self) -> list[EvaluatedPaper]:
        today = datetime.now().astimezone().date().isoformat()
        print(f"Task: {today}")

        if not self.seen_store.is_initialized:
            self.seen_store.initialize(today)
            print(
                f"Initialized paper baseline at {today}; "
                "papers published on or before this date are skipped."
            )
            return []

        fetched = deduplicate_by_id(self._fetch())
        baseline_date = self.seen_store.baseline_date
        if baseline_date is None:
            raise RuntimeError("Seen-paper baseline is unavailable")
        new_papers = [
            paper
            for paper in self.seen_store.exclude_seen(fetched)
            if paper["published"] > baseline_date
        ]
        print(f"Fetched papers: {len(fetched)}; new papers: {len(new_papers)}")

        criteria = self.config.criteria_path.read_text(encoding="utf-8")
        related = [paper for paper in new_papers if self.llm.matches(paper, criteria)]
        print(f"Related papers: {len(related)}")

        evaluated = [
            EvaluatedPaper(
                paper=paper,
                quality=self.llm.assess_quality(
                    paper,
                    threshold=self.config.quality.threshold,
                ),
            )
            for paper in related
        ]

        # The digest is the transaction boundary. A failure leaves IDs unseen.
        self.publisher.publish_digest(self.config.paper.tag, evaluated)
        self.seen_store.commit(paper["id"] for paper in new_papers)

        for item in self._reading_candidates(evaluated):
            self._publish_reading(item)
        return evaluated

    def _fetch(self) -> list[Paper]:
        papers: list[Paper] = []
        for category in self.config.paper.categories:
            papers.extend(
                self.fetcher(
                    category,
                    self.config.paper.max_results_per_category,
                )
            )
        return papers

    def _reading_candidates(self, papers: list[EvaluatedPaper]) -> list[EvaluatedPaper]:
        important = [
            item
            for item in papers
            if item.quality is not None and item.quality.is_important
        ]
        important.sort(
            key=lambda item: item.quality.total if item.quality else -1,
            reverse=True,
        )
        return important[: self.config.quality.max_readings_per_run]

    def _publish_reading(self, item: EvaluatedPaper) -> None:
        try:
            full_text = self.text_extractor.extract(item.paper)
            reading = self.llm.create_reading(
                item.paper,
                full_text=full_text,
                chunk_characters=self.config.reading.chunk_characters,
            )
        except Exception as error:  # noqa: BLE001
            print(f'Reading generation failed for "{item.paper["title"]}": {error}')
            reading = PaperReading(
                content=(
                    "### 精读生成失败\n"
                    "系统未能生成精读，以下保留论文原始摘要供参考。\n\n"
                    f"{item.paper['abstract']}"
                ),
                source="generation_failed",
            )
        try:
            self.publisher.publish_reading(item, reading)
        except LarkPublishError as error:
            print(f'Failed to publish reading for "{item.paper["title"]}": {error}')
