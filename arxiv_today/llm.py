"""OpenAI-compatible LLM operations for the paper pipeline."""

from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .config import LLMConfig
from .models import Paper, PaperReading, QualityAssessment, ReadingSource
from .prompts import (
    quality_prompt,
    reading_chunk_prompt,
    reading_synthesis_prompt,
    related_prompt,
)


class _RelatedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    related: bool


class _QualityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    novelty: int = Field(ge=0, le=25)
    technical_depth: int = Field(ge=0, le=25)
    experimental_credibility: int = Field(ge=0, le=20)
    potential_impact: int = Field(ge=0, le=20)
    author_signal: int = Field(ge=0, le=10)
    one_sentence: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class LLMService:
    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = OpenAI(
            api_key=config.effective_api_key,
            base_url=config.base_url,
        )

    def complete(self, prompt: str, *, model: str) -> str | None:
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                stream=False,
            )
            content = response.choices[0].message.content
            return content.strip() if content else None
        except Exception as error:  # noqa: BLE001
            print(f"LLM Server Error: {error}")
            return None

    def matches(self, paper: Paper, criteria: str) -> bool:
        response = self.complete(
            related_prompt(paper["title"], paper["abstract"], criteria),
            model=self.config.effective_related_model,
        )
        try:
            result = _RelatedResponse.model_validate(self._json_object(response))
            return result.related
        except (TypeError, ValueError, ValidationError) as error:
            print(
                f'Related evaluation failed for "{paper["title"]}": {error}. '
                "Treating it as unrelated."
            )
            return False

    def assess_quality(
        self,
        paper: Paper,
        *,
        threshold: int,
    ) -> QualityAssessment | None:
        response = self.complete(
            quality_prompt(paper["title"], paper["abstract"], paper["authors"]),
            model=self.config.effective_quality_model,
        )
        try:
            raw = _QualityResponse.model_validate(self._json_object(response))
        except (TypeError, ValueError, ValidationError) as error:
            print(f'Quality evaluation failed for "{paper["title"]}": {error}')
            return None

        total = (
            raw.novelty
            + raw.technical_depth
            + raw.experimental_credibility
            + raw.potential_impact
            + raw.author_signal
        )
        return QualityAssessment(
            **raw.model_dump(),
            total=total,
            is_important=total >= threshold,
        )

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
        )
        if response:
            content = self._remove_thinking(response)
            if len(content) > 2_500:
                content = f"{content[:2_450].rstrip()}\n\n> 内容已按卡片长度截断。"
            return PaperReading(content=content, source=source)
        return PaperReading(
            content=(
                "### 精读生成失败\n"
                "LLM 未能生成精读，以下保留论文原始摘要供参考。\n\n"
                f"{paper['abstract']}"
            ),
            source="generation_failed",
        )

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
            )
            if note:
                notes.append(self._remove_thinking(note))
        if notes:
            return "\n\n".join(notes), "full_text"
        return paper["abstract"], "abstract_fallback"

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
