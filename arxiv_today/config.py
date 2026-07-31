"""Validated application configuration."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, ValidationError
from pydantic.functional_validators import model_validator

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


class ConfigError(ValueError):
    """Raised when the application configuration is invalid."""


class ConfigModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class LarkConfig(ConfigModel):
    app_id: str
    app_secret: str
    target_chat_id: str
    template_id: str | None = None
    template_version_name: str | None = None
    main_card_batch_size: PositiveInt = 50


class PaperConfig(ConfigModel):
    tag: str
    categories: tuple[str, ...]
    max_results_per_category: PositiveInt = 100
    history_file: str = "papers.json"
    seen_file: str = "seen_papers.json"
    criteria_file: str = "paper_to_hunt.md"


class LLMConfig(ConfigModel):
    model: str
    base_url: str
    api_key: str = ""
    related_model: str | None = None
    recommendation_model: str | None = None
    reading_model: str | None = None
    related_max_tokens: PositiveInt = 800
    recommendation_max_tokens: PositiveInt = 1_200
    reading_chunk_max_tokens: PositiveInt = 1_500
    reading_max_tokens: PositiveInt = 3_000

    @property
    def effective_api_key(self) -> str:
        return self.api_key or "ollama"

    @property
    def effective_related_model(self) -> str:
        return self.related_model or self.model

    @property
    def effective_recommendation_model(self) -> str:
        return self.recommendation_model or self.model

    @property
    def effective_reading_model(self) -> str:
        return self.reading_model or self.model


class RecommendationConfig(ConfigModel):
    related_batch_size: PositiveInt = 10
    selection_batch_size: PositiveInt = 30
    max_recommendations: int = Field(default=5, ge=0, le=5)

    @model_validator(mode="after")
    def validate_selection_batch(self) -> RecommendationConfig:
        if (
            self.max_recommendations > 0
            and self.selection_batch_size <= self.max_recommendations
        ):
            raise ValueError(
                "selection_batch_size must be greater than max_recommendations"
            )
        return self


class ReadingConfig(ConfigModel):
    pdf_timeout_seconds: PositiveInt = 30
    chunk_characters: PositiveInt = 12_000
    cache_dir: str = "reading_cache"


class AppConfig(ConfigModel):
    lark: LarkConfig
    paper: PaperConfig
    llm: LLMConfig
    recommendation: RecommendationConfig = Field(
        default_factory=RecommendationConfig
    )
    reading: ReadingConfig = Field(default_factory=ReadingConfig)
    base_dir: Path = Field(exclude=True)

    @property
    def history_path(self) -> Path:
        return self._resolve(self.paper.history_file)

    @property
    def seen_path(self) -> Path:
        return self._resolve(self.paper.seen_file)

    @property
    def criteria_path(self) -> Path:
        return self._resolve(self.paper.criteria_file)

    @property
    def reading_cache_path(self) -> Path:
        return self._resolve(self.reading.cache_dir)

    def _resolve(self, path: str) -> Path:
        candidate = Path(path).expanduser()
        return candidate if candidate.is_absolute() else self.base_dir / candidate

    @classmethod
    def load(cls, path: str | Path | None = None) -> AppConfig:
        source = DEFAULT_CONFIG_PATH if path is None else Path(path)
        config_path = source.expanduser().resolve()
        with config_path.open("r", encoding="utf-8") as file:
            values: object = yaml.safe_load(file)
        if not isinstance(values, Mapping):
            raise ConfigError("Configuration root must be a mapping")
        return cls.from_mapping(values, base_dir=config_path.parent)

    @classmethod
    def from_mapping(
        cls, values: Mapping[str, object], base_dir: str | Path = "."
    ) -> AppConfig:
        try:
            configured = cls.apply_environment(values)
            return cls.model_validate(
                {**configured, "base_dir": Path(base_dir).expanduser().resolve()}
            )
        except ValidationError as error:
            raise ConfigError(f"Invalid configuration:\n{error}") from error

    @staticmethod
    def apply_environment(values: Mapping[str, object]) -> dict[str, object]:
        """Apply secret/runtime overrides without writing them to YAML."""
        configured = dict(values)
        lark = configured.get("lark")
        llm = configured.get("llm")
        if isinstance(lark, Mapping):
            lark_values = dict(lark)
            lark_overrides = {
                "app_id": os.getenv("ARXIVTODAY_LARK_APP_ID"),
                "app_secret": os.getenv("ARXIVTODAY_LARK_APP_SECRET"),
                "target_chat_id": os.getenv("ARXIVTODAY_LARK_CHAT_ID"),
            }
            lark_values.update(
                {name: value for name, value in lark_overrides.items() if value}
            )
            configured["lark"] = lark_values
        if isinstance(llm, Mapping):
            llm_values = dict(llm)
            overrides = {
                "base_url": os.getenv("ARXIVTODAY_LLM_BASE_URL"),
                "api_key": os.getenv("ARXIVTODAY_LLM_API_KEY"),
                "model": os.getenv("ARXIVTODAY_LLM_MODEL"),
                "related_model": os.getenv("ARXIVTODAY_RELATED_MODEL"),
                "recommendation_model": (
                    os.getenv("ARXIVTODAY_RECOMMENDATION_MODEL")
                    or os.getenv("ARXIVTODAY_QUALITY_MODEL")
                ),
                "reading_model": os.getenv("ARXIVTODAY_READING_MODEL"),
            }
            llm_values.update(
                {name: value for name, value in overrides.items() if value}
            )
            configured["llm"] = llm_values
        return configured

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_config(cls, values: object) -> object:
        if not isinstance(values, Mapping):
            return values

        if any(name in values for name in ("lark", "paper", "llm")):
            normalized = dict(values)
            normalized.pop("features", None)
            normalized.pop("quality", None)
            paper = normalized.get("paper")
            if isinstance(paper, Mapping):
                normalized["paper"] = {
                    key: value for key, value in paper.items() if key != "keywords"
                }
            lark = normalized.get("lark")
            if isinstance(lark, Mapping):
                normalized["lark"] = {
                    key: value
                    for key, value in lark.items()
                    if key != "webhook_url"
                }
            llm = normalized.get("llm")
            if isinstance(llm, Mapping):
                llm_values = dict(llm)
                legacy_model = llm_values.pop("quality_model", None)
                if (
                    legacy_model is not None
                    and "recommendation_model" not in llm_values
                ):
                    llm_values["recommendation_model"] = legacy_model
                normalized["llm"] = llm_values
            return normalized

        return {
            "lark": {
                "app_id": values.get("app_id"),
                "app_secret": values.get("app_secret"),
                "target_chat_id": values.get("target_chat_id"),
                "template_id": values.get("template_id"),
                "template_version_name": values.get("template_version_name"),
            },
            "paper": {
                "tag": values.get("tag"),
                "categories": values.get("category_list"),
            },
            "llm": {
                "model": values.get("model"),
                "base_url": values.get("base_url"),
                "api_key": values.get("api_key", ""),
            },
            "base_dir": values.get("base_dir", "."),
        }
