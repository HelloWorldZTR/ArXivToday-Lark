from unittest import TestCase
from unittest.mock import patch

from arxiv_today.config import AppConfig


class AppConfigTest(TestCase):
    def test_loads_new_configuration_and_stage_model_fallbacks(self) -> None:
        config = AppConfig.from_mapping(
            {
                "lark": {
                    "webhook_url": "https://example.test/hook",
                    "template_id": "template",
                    "template_version_name": "1.0.0",
                },
                "paper": {
                    "tag": "AI",
                    "categories": ["cs.AI"],
                },
                "llm": {
                    "model": "default-model",
                    "quality_model": "quality-model",
                    "base_url": "http://localhost/v1",
                    "api_key": "",
                },
                "quality": {
                    "threshold": 80,
                    "max_readings_per_run": 3,
                },
            },
            base_dir="/tmp/project",
        )

        self.assertEqual(config.paper.categories, ("cs.AI",))
        self.assertEqual(config.llm.effective_api_key, "ollama")
        self.assertEqual(config.llm.effective_related_model, "default-model")
        self.assertEqual(config.llm.effective_quality_model, "quality-model")
        self.assertEqual(config.quality.threshold, 80)
        self.assertEqual(config.seen_path, config.base_dir / "seen_papers.json")

    def test_ignores_removed_fields_in_previous_nested_config(self) -> None:
        config = AppConfig.from_mapping(
            {
                "lark": {
                    "webhook_url": "https://example.test/hook",
                    "template_id": "template",
                    "template_version_name": "1.0.0",
                },
                "paper": {
                    "tag": "AI",
                    "categories": ["cs.AI"],
                    "keywords": ["legacy"],
                },
                "llm": {
                    "model": "model",
                    "base_url": "http://localhost/v1",
                },
                "features": {
                    "llm_filtering": True,
                    "llm_translation": True,
                },
            }
        )

        self.assertEqual(config.paper.categories, ("cs.AI",))
        self.assertEqual(config.quality.threshold, 75)

    def test_environment_overrides_secrets_and_endpoint(self) -> None:
        values = {
            "lark": {"webhook_url": "yaml-webhook"},
            "paper": {"tag": "AI", "categories": ["cs.AI"]},
            "llm": {
                "model": "yaml-model",
                "base_url": "yaml-url",
                "api_key": "yaml-key",
            },
        }
        with patch.dict(
            "os.environ",
            {
                "ARXIVTODAY_WEBHOOK_URL": "env-webhook",
                "ARXIVTODAY_LLM_BASE_URL": "env-url",
                "ARXIVTODAY_LLM_API_KEY": "env-key",
            },
        ):
            config = AppConfig.from_mapping(values)

        self.assertEqual(config.lark.webhook_url, "env-webhook")
        self.assertEqual(config.llm.base_url, "env-url")
        self.assertEqual(config.llm.api_key, "env-key")
