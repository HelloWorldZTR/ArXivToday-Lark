from unittest import TestCase

from arxiv_today.config import LarkConfig
from arxiv_today.lark import LarkPublisher
from arxiv_today.models import EvaluatedPaper, PaperReading
from tests.test_pipeline import make_paper, quality


class LarkPublisherTest(TestCase):
    def _publisher(self) -> LarkPublisher:
        return LarkPublisher(
            LarkConfig(
                webhook_url="url",
                template_id="AAqWNxGgDjV5N",
                template_version_name="1.0.0",
            )
        )

    def test_reading_card_uses_collapsible_panel(self) -> None:
        publisher = self._publisher()
        evaluated = EvaluatedPaper(make_paper("paper"), quality(85))
        payload = publisher._reading_payload(
            evaluated,
            PaperReading(content="reading", source="full_text"),
        )

        card = payload["card"]
        panel = card["body"]["elements"][1]
        self.assertEqual(panel["tag"], "collapsible_panel")
        self.assertFalse(panel["expanded"])
        self.assertEqual(panel["elements"][0]["content"], "reading")

    def test_digest_uses_published_template_with_full_title(self) -> None:
        publisher = self._publisher()
        evaluated = EvaluatedPaper(make_paper("paper"), quality(85))

        payload = publisher._digest_payload(
            "AI",
            [evaluated],
            total_papers=1,
            start_index=1,
        )

        data = payload["card"]["data"]
        self.assertEqual(data["template_id"], "AAqWNxGgDjV5N")
        variables = data["template_variable"]
        self.assertIn("title paper", variables["table_rows"][0]["paper"])
        self.assertIn("arXiv: paper", variables["table_rows"][0]["paper"])
