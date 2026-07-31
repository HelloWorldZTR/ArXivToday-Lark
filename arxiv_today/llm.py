"""OpenAI-compatible LLM operations for the paper pipeline."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any, Literal

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .config import LLMConfig
from .models import Paper, PaperReading, ReadingSource, Recommendation, Relevance
from .prompts import (
    reading_chunk_prompt,
    reading_synthesis_prompt,
    recommendation_prompt,
    related_batch_prompt,
)


class LLMResponseError(RuntimeError):
    """Raised when a required LLM response cannot be validated."""


class _RelatedItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    relevance: Literal["related", "possible", "unrelated"]


class _RelatedBatchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    results: list[_RelatedItem]


class _RecommendationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    summary: str = Field(min_length=1)


class _RecommendationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendations: list[_RecommendationItem]


class LLMService:
    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = OpenAI(
            api_key=config.effective_api_key,
            base_url=config.base_url,
        )

    def complete(
        self,
        prompt: str,
        *,
        model: str,
        max_tokens: int,
    ) -> str | None:
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                stream=False,
                temperature=0,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content
            return content.strip() if content else None
        except Exception as error:  # noqa: BLE001
            print(f"LLM Server Error: {error}")
            return None

    def classify_related(
        self,
        papers: list[Paper],
        criteria: str,
        *,
        batch_size: int,
    ) -> dict[str, Relevance]:
        classifications: dict[str, Relevance] = {}
        for batch in self._batches(papers, batch_size):
            batch_results = self._classify_batch(batch, criteria)
            missing = [
                paper for paper in batch if paper["id"] not in batch_results
            ]
            if missing:
                print(
                    "Retrying missing relevance results: "
                    + ", ".join(paper["id"] for paper in missing)
                )
                batch_results.update(self._classify_batch(missing, criteria))
            still_missing = [
                paper["id"]
                for paper in batch
                if paper["id"] not in batch_results
            ]
            if still_missing:
                raise LLMResponseError(
                    "Missing relevance results after retry: "
                    + ", ".join(still_missing)
                )
            classifications.update(batch_results)
        return classifications

    def select_recommendations(
        self,
        papers: list[Paper],
        criteria: str,
        *,
        limit: int,
        batch_size: int,
    ) -> list[Recommendation]:
        if not papers or limit == 0:
            return []

        current = papers
        while len(current) > batch_size:
            semifinalists: list[Paper] = []
            for batch in self._batches(current, batch_size):
                recommendations = self._select_once(
                    batch,
                    criteria,
                    limit=limit,
                )
                selected_ids = {item.paper_id for item in recommendations}
                semifinalists.extend(
                    paper for paper in batch if paper["id"] in selected_ids
                )
            current = semifinalists
            if not current:
                return []

        return self._select_once(current, criteria, limit=limit)

    def _classify_batch(
        self,
        papers: list[Paper],
        criteria: str,
    ) -> dict[str, Relevance]:
        response = self.complete(
            related_batch_prompt(papers, criteria),
            model=self.config.effective_related_model,
            max_tokens=self.config.related_max_tokens,
        )
        try:
            raw = _RelatedBatchResponse.model_validate(self._json_object(response))
        except (TypeError, ValueError, ValidationError) as error:
            print(f"Related batch evaluation failed: {error}")
            return {}

        expected_ids = {paper["id"] for paper in papers}
        results: dict[str, Relevance] = {}
        for item in raw.results:
            if item.id not in expected_ids:
                print(f"Related batch returned unknown paper ID: {item.id}")
                return {}
            if item.id in results:
                print(f"Related batch returned duplicate paper ID: {item.id}")
                return {}
            results[item.id] = item.relevance
        return results

    def _select_once(
        self,
        papers: list[Paper],
        criteria: str,
        *,
        limit: int,
    ) -> list[Recommendation]:
        response = self.complete(
            recommendation_prompt(papers, criteria, limit=limit),
            model=self.config.effective_recommendation_model,
            max_tokens=self.config.recommendation_max_tokens,
        )
        try:
            raw = _RecommendationResponse.model_validate(
                self._json_object(response)
            )
        except (TypeError, ValueError, ValidationError) as error:
            raise LLMResponseError(
                f"Recommendation evaluation failed: {error}"
            ) from error

        expected_ids = {paper["id"] for paper in papers}
        recommendations: list[Recommendation] = []
        selected_ids: set[str] = set()
        for item in raw.recommendations:
            if item.id not in expected_ids:
                raise LLMResponseError(
                    f"Recommendation returned unknown paper ID: {item.id}"
                )
            if item.id in selected_ids:
                raise LLMResponseError(
                    f"Recommendation returned duplicate paper ID: {item.id}"
                )
            selected_ids.add(item.id)
            summary = re.sub(r"\s+", " ", item.summary).strip()[:60].rstrip()
            if not summary:
                raise LLMResponseError(
                    f"Recommendation summary is empty for paper ID: {item.id}"
                )
            recommendations.append(
                Recommendation(paper_id=item.id, summary=summary)
            )
        if len(recommendations) > limit:
            raise LLMResponseError(
                f"Recommendation returned {len(recommendations)} papers; "
                f"limit is {limit}"
            )
        return recommendations

    def create_reading(
        self,
        paper: Paper,
        *,
        full_text: str | None,
        chunk_characters: int,
    ) -> PaperReading:
        material, source = self._reading_material(
            paper,
            full_text=full_text,
            chunk_characters=chunk_characters,
        )
        response = self.complete(
            reading_synthesis_prompt(
                title=paper["title"],
                authors=paper["authors"],
                abstract=paper["abstract"],
                material=material,
                source_label=(
                    "PDF 全文分块笔记"
                    if source == "full_text"
                    else "标题、摘要与作者（PDF 获取失败后的降级材料）"
                ),
            ),
            model=self.config.effective_reading_model,
            max_tokens=self.config.reading_max_tokens,
        )
        if response:
            content = self._remove_thinking(response)
            if len(content) > 2_500:
                content = f"{content[:2_450].rstrip()}\n\n> 内容已按卡片长度截断。"
            return PaperReading(content=content, source=source)
        raise LLMResponseError("LLM did not generate a reading")

    def _reading_material(
        self,
        paper: Paper,
        *,
        full_text: str | None,
        chunk_characters: int,
    ) -> tuple[str, ReadingSource]:
        if not full_text:
            return paper["abstract"], "abstract_fallback"

        chunks = [
            full_text[index : index + chunk_characters]
            for index in range(0, len(full_text), chunk_characters)
        ]
        notes: list[str] = []
        for index, chunk in enumerate(chunks, start=1):
            note = self.complete(
                reading_chunk_prompt(
                    paper["title"],
                    chunk,
                    index,
                    len(chunks),
                ),
                model=self.config.effective_reading_model,
                max_tokens=self.config.reading_chunk_max_tokens,
            )
            if note:
                notes.append(self._remove_thinking(note))
        if notes:
            return "\n\n".join(notes), "full_text"
        return paper["abstract"], "abstract_fallback"

    @staticmethod
    def _batches(items: list[Paper], size: int) -> Iterable[list[Paper]]:
        for index in range(0, len(items), size):
            yield items[index : index + size]

    @classmethod
    def _json_object(cls, response: str | None) -> dict[str, Any]:
        if not response:
            raise ValueError("empty LLM response")
        text = cls._remove_thinking(response)
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise ValueError("response does not contain a JSON object")
        value = json.loads(match.group(0))
        if not isinstance(value, dict):
            raise TypeError("LLM JSON response must be an object")
        return value

    @staticmethod
    def _remove_thinking(text: str) -> str:
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
