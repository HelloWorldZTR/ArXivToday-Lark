from unittest import TestCase

from pydantic import ValidationError

from arxiv_today.models import Paper, Recommendation


class PaperModelTest(TestCase):
    def test_all_paper_fields_are_required(self) -> None:
        self.assertEqual(
            Paper.__required_keys__,
            frozenset(
                {
                    "title",
                    "id",
                    "abstract",
                    "authors",
                    "url",
                    "published",
                    "version",
                }
            ),
        )
        self.assertEqual(Paper.__optional_keys__, frozenset())

    def test_recommendation_summary_is_limited(self) -> None:
        with self.assertRaises(ValidationError):
            Recommendation(paper_id="2601.00001", summary="长" * 61)
