from unittest import TestCase
from unittest.mock import patch

from pydantic import ValidationError

from arxiv_today.config import AppConfig


def config_values() -> dict[str, object]:
    return {
        "lark": {
            "app_id": "app",
            "app_secret": "secret",
            "target_chat_id": "chat",
            "template_id": "template",
            "template_version_name": "1.0.0",
        },
        "paper": {
            "tag": "AI",
            "categories": ["cs.AI"],
        },
        "llm": {
            "model": "default-model",
            "recommendation_model": "recommendation-model",
            "base_url": "https://api.example/v1",
            "api_key": "",
        },
        "recommendation": {
            "related_batch_size": 10,
            "selection_batch_size": 30,
            "max_recommendations": 5,
        },
    }


class AppConfigTest(TestCase):
    def test_loads_new_configuration_and_stage_model_fallbacks(self) -> None:
        config = AppConfig.from_mapping(
            config_values(),
            base_dir="/tmp/project",
        )

        self.assertEqual(config.paper.categories, ("cs.AI",))
        self.assertEqual(config.llm.effective_api_key, "ollama")
        self.assertEqual(config.llm.effective_related_model, "default-model")
        self.assertEqual(
            config.llm.effective_recommendation_model,
            "recommendation-model",
        )
        self.assertEqual(config.recommendation.related_batch_size, 10)
        self.assertEqual(config.seen_path, config.base_dir / "seen_papers.json")
        self.assertEqual(
            config.reading_cache_path,
            config.base_dir / "reading_cache",
        )

    def test_migrates_legacy_quality_model_and_removed_fields(self) -> None:
        values = config_values()
        values["features"] = {"llm_filtering": True}
        values["quality"] = {"threshold": 80}
        values["paper"] = {
            "tag": "AI",
            "categories": ["cs.AI"],
            "keywords": ["legacy"],
        }
        values["llm"] = {
            "model": "model",
            "quality_model": "legacy-quality",
            "base_url": "https://api.example/v1",
        }

        config = AppConfig.from_mapping(values)

        self.assertEqual(config.paper.categories, ("cs.AI",))
        self.assertEqual(
            config.llm.effective_recommendation_model,
            "legacy-quality",
        )
        self.assertEqual(config.recommendation.max_recommendations, 5)

    def test_environment_overrides_lark_and_llm_secrets(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "ARXIVTODAY_LARK_APP_ID": "env-app",
                "ARXIVTODAY_LARK_APP_SECRET": "env-secret",
                "ARXIVTODAY_LARK_CHAT_ID": "env-chat",
                "ARXIVTODAY_LLM_BASE_URL": "env-url",
                "ARXIVTODAY_LLM_API_KEY": "env-key",
            },
        ):
            config = AppConfig.from_mapping(config_values())

        self.assertEqual(config.lark.app_id, "env-app")
        self.assertEqual(config.lark.app_secret, "env-secret")
        self.assertEqual(config.lark.target_chat_id, "env-chat")
        self.assertEqual(config.llm.base_url, "env-url")
        self.assertEqual(config.llm.api_key, "env-key")

    def test_selection_batch_must_reduce_recursive_candidates(self) -> None:
        values = config_values()
        values["recommendation"] = {
            "related_batch_size": 10,
            "selection_batch_size": 5,
            "max_recommendations": 5,
        }

        with self.assertRaises(ValidationError):
            AppConfig.model_validate({**values, "base_dir": "."})
