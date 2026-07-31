from unittest import TestCase
from unittest.mock import patch

from arxiv_today.config import LLMConfig
from arxiv_today.llm import LLMResponseError, LLMService
from arxiv_today.models import Paper, Recommendation
from tests.test_pipeline import make_paper


class LLMServiceTest(TestCase):
    def setUp(self) -> None:
        self.service = LLMService(
            LLMConfig(
                model="default",
                related_model="related",
                recommendation_model="recommendation",
                reading_model="reading",
                base_url="https://api.example/v1",
                api_key="key",
            )
        )

    def test_25_papers_are_classified_in_10_10_5_batches(self) -> None:
        papers = [make_paper(str(index)) for index in range(25)]
        batch_sizes: list[int] = []

        def classify(batch: list[Paper], _criteria: str):
            batch_sizes.append(len(batch))
            return {paper["id"]: "related" for paper in batch}

        with patch.object(self.service, "_classify_batch", side_effect=classify):
            result = self.service.classify_related(
                papers,
                "criteria",
                batch_size=10,
            )

        self.assertEqual(batch_sizes, [10, 10, 5])
        self.assertEqual(len(result), 25)

    def test_only_missing_relevance_results_are_retried(self) -> None:
        papers = [make_paper("1"), make_paper("2"), make_paper("3")]
        calls: list[list[str]] = []

        def classify(batch: list[Paper], _criteria: str):
            calls.append([paper["id"] for paper in batch])
            if len(calls) == 1:
                return {"1": "related"}
            return {paper["id"]: "possible" for paper in batch}

        with patch.object(self.service, "_classify_batch", side_effect=classify):
            result = self.service.classify_related(
                papers,
                "criteria",
                batch_size=10,
            )

        self.assertEqual(calls, [["1", "2", "3"], ["2", "3"]])
        self.assertEqual(result["2"], "possible")

    def test_missing_relevance_after_retry_aborts(self) -> None:
        with (
            patch.object(self.service, "_classify_batch", return_value={}),
            self.assertRaises(LLMResponseError),
        ):
            self.service.classify_related(
                [make_paper("1")],
                "criteria",
                batch_size=10,
            )

    def test_recommendation_is_structured_limited_and_uses_stage_model(self) -> None:
        response = (
            '{"recommendations":[{"id":"1","summary":"'
            + "摘要" * 40
            + '"}]}'
        )
        with patch.object(self.service, "complete", return_value=response) as complete:
            result = self.service.select_recommendations(
                [make_paper("1")],
                "criteria",
                limit=5,
                batch_size=30,
            )

        self.assertEqual(result[0].paper_id, "1")
        self.assertLessEqual(len(result[0].summary), 60)
        self.assertEqual(complete.call_args.kwargs["model"], "recommendation")

    def test_large_recommendation_pool_is_reduced_before_final_selection(
        self,
    ) -> None:
        papers = [make_paper(str(index)) for index in range(61)]
        batch_sizes: list[int] = []

        def select(batch, _criteria, *, limit):
            batch_sizes.append(len(batch))
            return [
                Recommendation(
                    paper_id=paper["id"],
                    summary=f"summary {paper['id']}",
                )
                for paper in batch[:limit]
            ]

        with patch.object(self.service, "_select_once", side_effect=select):
            result = self.service.select_recommendations(
                papers,
                "criteria",
                limit=5,
                batch_size=30,
            )

        self.assertEqual(batch_sizes, [30, 30, 1, 11])
        self.assertEqual(len(result), 5)

    def test_reading_generation_failure_is_reported(self) -> None:
        with (
            patch.object(self.service, "complete", return_value=None),
            self.assertRaises(LLMResponseError),
        ):
            self.service.create_reading(
                make_paper("1"),
                full_text=None,
                chunk_characters=100,
            )
