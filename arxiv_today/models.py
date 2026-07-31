"""Shared data models."""

from dataclasses import dataclass
from typing import Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field

ReadingSource = Literal["full_text", "abstract_fallback"]
Relevance = Literal["related", "possible", "unrelated"]


class Paper(TypedDict):
    """An arXiv paper with every pipeline field required."""

    title: str
    id: str
    abstract: str
    authors: tuple[str, ...]
    url: str
    published: str
    version: str


class Recommendation(BaseModel):
    """A paper selected by the comparative recommendation stage."""

    model_config = ConfigDict(frozen=True)

    paper_id: str = Field(min_length=1)
    summary: str = Field(min_length=1, max_length=60)


class PaperReading(BaseModel):
    """Content rendered in an important paper's follow-up card."""

    model_config = ConfigDict(frozen=True)

    content: str = Field(min_length=1)
    source: ReadingSource


@dataclass(frozen=True)
class DigestPaper:
    """A paper displayed in the digest, optionally as a recommendation."""

    paper: Paper
    recommendation: Recommendation | None = None
