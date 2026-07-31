"""The complete paper collection and delivery pipeline."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from .config import AppConfig
from .lark import LarkPublisher
from .llm import LLMService
from .models import DigestPaper, Paper, Recommendation, Relevance
from .papers import SeenPaperStore, deduplicate_by_id, fetch_latest_papers

PaperFetcher = Callable[[str, int], list[Paper]]


class LLMOperations(Protocol):
    def classify_related(
        self,
        papers: list[Paper],
        criteria: str,
        *,
        batch_size: int,
    ) -> dict[str, Relevance]: ...

    def select_recommendations(
        self,
        papers: list[Paper],
        criteria: str,
        *,
        limit: int,
        batch_size: int,
    ) -> list[Recommendation]: ...


class PublisherOperations(Protocol):
    def publish_digest(self, tag: str, papers: list[DigestPaper]) -> None: ...


class PaperPipeline:
    """Coordinates the one-shot fetch, classify, recommend, and publish workflow."""

    def __init__(
        self,
        config: AppConfig,
        *,
        fetcher: PaperFetcher = fetch_latest_papers,
        llm: LLMOperations | None = None,
        publisher: PublisherOperations | None = None,
        seen_store: SeenPaperStore | None = None,
    ):
        self.config = config
        self.fetcher = fetcher
        self.llm = llm or LLMService(config.llm)
        self.publisher = publisher or LarkPublisher(config.lark)
        self.seen_store = seen_store or SeenPaperStore(
            config.seen_path,
            legacy_history_path=config.history_path,
        )

    def run(self) -> list[DigestPaper]:
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
        relevance = self.llm.classify_related(
            new_papers,
            criteria,
            batch_size=self.config.recommendation.related_batch_size,
        )
        related = [
            paper
            for paper in new_papers
            if relevance[paper["id"]] == "related"
        ]
        candidates = [
            paper
            for paper in new_papers
            if relevance[paper["id"]] in ("related", "possible")
        ]
        recommendations = self.llm.select_recommendations(
            candidates,
            criteria,
            limit=self.config.recommendation.max_recommendations,
            batch_size=self.config.recommendation.selection_batch_size,
        )
        print(
            f"Related papers: {len(related)}; "
            f"possible papers: {len(candidates) - len(related)}; "
            f"recommendations: {len(recommendations)}"
        )

        paper_by_id = {paper["id"]: paper for paper in candidates}
        recommendation_by_id = {
            recommendation.paper_id: recommendation
            for recommendation in recommendations
        }
        recommended = [
            DigestPaper(
                paper=paper_by_id[recommendation.paper_id],
                recommendation=recommendation,
            )
            for recommendation in recommendations
        ]
        recommended_ids = set(recommendation_by_id)
        digest = recommended + [
            DigestPaper(paper=paper)
            for paper in related
            if paper["id"] not in recommended_ids
        ]

        # The digest is the transaction boundary. A failure leaves IDs unseen.
        self.publisher.publish_digest(self.config.paper.tag, digest)
        self.seen_store.commit(paper["id"] for paper in new_papers)
        return digest

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
