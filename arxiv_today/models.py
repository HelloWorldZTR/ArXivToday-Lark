"""Shared data models."""

from typing import TypedDict


class _RequiredPaperFields(TypedDict):
    title: str
    id: str
    abstract: str
    url: str
    published: str


class Paper(_RequiredPaperFields, total=False):
    """An arXiv paper with an optional translated abstract."""

    zh_abstract: str | None
