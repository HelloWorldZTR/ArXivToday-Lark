"""Shared data models."""

from dataclasses import dataclass
from typing import Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, model_validator

ReadingSource = Literal["full_text", "abstract_fallback", "generation_failed"]


class Paper(TypedDict):
    """An arXiv paper with every pipeline field required."""

    title: str
    id: str
    abstract: str
    authors: tuple[str, ...]
    url: str
    published: str


class QualityAssessment(BaseModel):
    """Validated result of the quality scoring stage."""

    model_config = ConfigDict(frozen=True)

    novelty: int = Field(ge=0, le=25)
    technical_depth: int = Field(ge=0, le=25)
    experimental_credibility: int = Field(ge=0, le=20)
    potential_impact: int = Field(ge=0, le=20)
    author_signal: int = Field(ge=0, le=10)
    total: int = Field(ge=0, le=100)
    one_sentence: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    is_important: bool

    @model_validator(mode="after")
    def validate_total(self) -> "QualityAssessment":
        expected = (
            self.novelty
            + self.technical_depth
            + self.experimental_credibility
            + self.potential_impact
            + self.author_signal
        )
        if self.total != expected:
            raise ValueError(f"quality total must equal component sum ({expected})")
        return self


class PaperReading(BaseModel):
    """Content rendered in an important paper's follow-up card."""

    model_config = ConfigDict(frozen=True)

    content: str = Field(min_length=1)
    source: ReadingSource


@dataclass(frozen=True)
class EvaluatedPaper:
    paper: Paper
    quality: QualityAssessment | None

    @property
    def quality_label(self) -> str:
        return str(self.quality.total) if self.quality else "评估失败"

    @property
    def one_sentence(self) -> str:
        if self.quality:
            return self.quality.one_sentence
        return "质量评估失败，仅作为 related 论文展示。"
