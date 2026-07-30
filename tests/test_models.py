from unittest import TestCase

from arxiv_today.models import Paper


class PaperModelTest(TestCase):
    def test_only_translation_is_optional(self) -> None:
        self.assertEqual(
            Paper.__required_keys__,
            frozenset({"title", "id", "abstract", "url", "published"}),
        )
        self.assertEqual(Paper.__optional_keys__, frozenset({"zh_abstract"}))
