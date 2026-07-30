from unittest import TestCase
from unittest.mock import patch

from arxiv_today.config import LLMConfig
from arxiv_today.llm import LLMService
from arxiv_today.models import Paper


def paper() -> Paper:
    return {
        "id": "1",
        "title": "Paper",
        "abstract": "Abstract",
        "authors": ("Unknown Author",),
        "url": "https://arxiv.org/abs/1",
        "published": "2026-01-01",
    }


class LLMServiceTest(TestCase):
    def setUp(self) -> None:
        self.service = LLMService(
            LLMConfig(
                model="default",
                related_model="related",
                quality_model="quality",
                reading_model="reading",
                base_url="http://localhost/v1",
                api_key="key",
            )
        )

    def test_related_invalid_response_is_unrelated(self) -> None:
        with patch.object(self.service, "complete", return_value="not-json"):
            self.assertFalse(self.service.matches(paper(), "criteria"))

    def test_quality_is_structured_and_thresholded(self) -> None:
        response = """{
            "novelty": 20,
            "technical_depth": 20,
            "experimental_credibility": 15,
            "potential_impact": 15,
            "author_signal": 5,
            "one_sentence": "值得关注",
            "reason": "结构完整"
        }"""
        with patch.object(self.service, "complete", return_value=response) as complete:
            result = self.service.assess_quality(paper(), threshold=75)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.total, 75)
        self.assertTrue(result.is_important)
        self.assertEqual(complete.call_args.kwargs["model"], "quality")

    def test_reading_generation_failure_keeps_original_abstract(self) -> None:
        with patch.object(self.service, "complete", return_value=None):
            result = self.service.create_reading(
                paper(),
                full_text=None,
                chunk_characters=100,
            )

        self.assertEqual(result.source, "generation_failed")
        self.assertIn("Abstract", result.content)
