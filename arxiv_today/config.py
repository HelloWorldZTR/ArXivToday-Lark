"""Validated application configuration."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, ValidationError
from pydantic.functional_validators import model_validator

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


class ConfigError(ValueError):
    """Raised when the application configuration is invalid."""


class ConfigModel(BaseModel):
    """Common behavior for every immutable configuration section."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class LarkConfig(ConfigModel):
    webhook_url: str
    template_id: str
    template_version_name: str


class PaperConfig(ConfigModel):
    tag: str
    categories: tuple[str, ...]
    keywords: tuple[str, ...] = ()
    max_results_per_category: PositiveInt = 100
    history_file: str = "papers.json"
    criteria_file: str = "paper_to_hunt.md"


class LLMConfig(ConfigModel):
    model: str
    base_url: str
    api_key: str = ""

    @property
    def effective_api_key(self) -> str:
        # OpenAI-compatible local services still require a non-empty SDK value.
        return self.api_key or "ollama"


class FeatureConfig(ConfigModel):
    llm_filtering: bool = True
    llm_translation: bool = True


class AppConfig(ConfigModel):
    lark: LarkConfig
    paper: PaperConfig
    llm: LLMConfig
    features: FeatureConfig = Field(default_factory=FeatureConfig)
    base_dir: Path = Field(exclude=True)

    @property
    def history_path(self) -> Path:
        return self._resolve(self.paper.history_file)

    @property
    def criteria_path(self) -> Path:
        return self._resolve(self.paper.criteria_file)

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
            return cls.model_validate(
                {**values, "base_dir": Path(base_dir).expanduser().resolve()}
            )
        except ValidationError as error:
            raise ConfigError(f"Invalid configuration:\n{error}") from error

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_config(cls, values: object) -> object:
        """Convert the old flat schema once, before validation begins."""
        if not isinstance(values, Mapping) or any(
            name in values for name in ("lark", "paper", "llm", "features")
        ):
            return values

        return {
            "lark": {
                "webhook_url": values.get("webhook_url"),
                "template_id": values.get("template_id"),
                "template_version_name": values.get("template_version_name"),
            },
            "paper": {
                "tag": values.get("tag"),
                "categories": values.get("category_list"),
                "keywords": values.get("keyword_list", []),
            },
            "llm": {
                "model": values.get("model"),
                "base_url": values.get("base_url"),
                "api_key": values.get("api_key", ""),
            },
            "features": {
                "llm_filtering": values.get("use_llm_for_filtering", True),
                "llm_translation": values.get("use_llm_for_translation", True),
            },
            "base_dir": values.get("base_dir", "."),
        }
