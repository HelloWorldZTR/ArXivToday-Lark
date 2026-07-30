"""The complete paper collection and delivery pipeline."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from tqdm import tqdm

from .config import AppConfig
from .lark import LarkPublisher
from .llm import LLMService
from .models import Paper
from .papers import (
    PaperHistory,
    deduplicate_by_id,
    fetch_latest_papers,
    filter_by_keywords,
)

PaperFetcher = Callable[[str, int], list[Paper]]


class PaperPipeline:
    """Coordinates each application step in one explicit place."""

    def __init__(
        self,
        config: AppConfig,
        *,
        fetcher: PaperFetcher = fetch_latest_papers,
        llm: LLMService | None = None,
        publisher: LarkPublisher | None = None,
        history: PaperHistory | None = None,
    ):
        self.config = config
        self.fetcher = fetcher
        self.history = history or PaperHistory(config.history_path)
        self.publisher = publisher or LarkPublisher(config.lark)
        self.llm = llm

        llm_is_needed = config.features.llm_filtering or config.features.llm_translation
        if llm_is_needed and self.llm is None:
            self.llm = LLMService(config.llm)

    def run(self) -> list[Paper]:
        today = datetime.now().astimezone().date().isoformat()
        print(f"Task: {today}")

        papers = self._fetch()
        print(f"Total papers: {len(papers)}")

        papers = deduplicate_by_id(papers)
        print(f"Deduplicated papers across categories: {len(papers)}")

        if self.config.paper.keywords:
            papers = filter_by_keywords(papers, self.config.paper.keywords)
        print(f"Filtered papers by Keyword: {len(papers)}")

        if self.config.features.llm_filtering:
            papers = self._filter_with_llm(papers)
            print(f"Filtered papers by LLM: {len(papers)}")

        papers = self.history.exclude_seen(papers)
        print(f"Deduplicated papers: {len(papers)}")

        if self.config.features.llm_translation:
            papers = self._translate(papers)
            print("Translated Abstracts into Chinese")

        self.history.prepend(papers)
        self.publisher.publish(self.config.paper.tag, papers)
        return papers

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

    def _filter_with_llm(self, papers: list[Paper]) -> list[Paper]:
        llm = self._require_llm()
        criteria = self.config.criteria_path.read_text(encoding="utf-8")
        return [paper for paper in papers if llm.matches(paper, criteria)]

    def _translate(self, papers: list[Paper]) -> list[Paper]:
        llm = self._require_llm()
        translated: list[Paper] = []
        for paper in tqdm(papers, desc="Translating Abstracts"):
            item = paper.copy()
            item["zh_abstract"] = llm.translate(paper["abstract"])
            translated.append(item)
        return translated

    def _require_llm(self) -> LLMService:
        if self.llm is None:
            raise RuntimeError("LLM service is not configured")
        return self.llm
