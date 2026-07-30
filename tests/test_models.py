from unittest import TestCase

from pydantic import ValidationError

from arxiv_today.models import Paper, QualityAssessment


class PaperModelTest(TestCase):
    def test_all_paper_fields_are_required(self) -> None:
        self.assertEqual(
            Paper.__required_keys__,
            frozenset({"title", "id", "abstract", "authors", "url", "published"}),
        )
        self.assertEqual(Paper.__optional_keys__, frozenset())

    def test_quality_total_must_match_components(self) -> None:
        with self.assertRaises(ValidationError):
            QualityAssessment(
                novelty=20,
                technical_depth=20,
                experimental_credibility=15,
                potential_impact=15,
                author_signal=5,
                total=74,
                one_sentence="评价",
                reason="理由",
                is_important=False,
            )
