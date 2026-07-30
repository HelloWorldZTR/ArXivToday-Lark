from unittest import TestCase

from arxiv_today.config import AppConfig


class AppConfigTest(TestCase):
    def test_loads_nested_configuration(self) -> None:
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
                    "keywords": ["agent"],
                },
                "llm": {
                    "model": "model",
                    "base_url": "http://localhost/v1",
                    "api_key": "",
                },
                "features": {
                    "llm_filtering": False,
                    "llm_translation": True,
                },
            },
            base_dir="/tmp/project",
        )

        self.assertEqual(config.paper.categories, ("cs.AI",))
        self.assertFalse(config.features.llm_filtering)
        self.assertEqual(config.llm.effective_api_key, "ollama")
        self.assertEqual(config.history_path, config.base_dir / "papers.json")

    def test_supports_legacy_flat_configuration(self) -> None:
        config = AppConfig.from_mapping(
            {
                "webhook_url": "https://example.test/hook",
                "template_id": "template",
                "template_version_name": "1.0.0",
                "tag": "AI",
                "category_list": ["cs.AI"],
                "keyword_list": [],
                "model": "model",
                "base_url": "http://localhost/v1",
                "api_key": "key",
                "use_llm_for_filtering": False,
                "use_llm_for_translation": False,
            }
        )

        self.assertEqual(config.paper.categories, ("cs.AI",))
        self.assertFalse(config.features.llm_filtering)
        self.assertFalse(config.features.llm_translation)
