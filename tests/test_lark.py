from unittest import TestCase

from arxiv_today.config import LarkConfig
from arxiv_today.lark import LarkPublisher, LarkPublishError
from arxiv_today.models import DigestPaper, PaperReading, Recommendation
from tests.test_pipeline import make_paper


class LarkPublisherTest(TestCase):
    def _publisher(self) -> LarkPublisher:
        return LarkPublisher(
            LarkConfig(
                app_id="app",
                app_secret="secret",
                target_chat_id="chat",
                template_id="AAqWNxGgDjV5N",
                template_version_name="1.0.0",
            ),
            client=object(),
        )

    def test_reading_card_uses_collapsible_panel_without_quality_score(self) -> None:
        publisher = self._publisher()
        card = publisher._reading_card(
            make_paper("paper"),
            PaperReading(content="reading", source="full_text"),
        )

        panel = card["body"]["elements"][1]
        self.assertEqual(panel["tag"], "collapsible_panel")
        self.assertFalse(panel["expanded"])
        self.assertEqual(panel["elements"][0]["content"], "reading")
        self.assertNotIn("Quality", str(card))

    def test_digest_only_lists_recommended_papers_below_table(self) -> None:
        publisher = self._publisher()
        papers = [
            DigestPaper(
                make_paper("recommended"),
                Recommendation(
                    paper_id="recommended",
                    summary="一句话摘要",
                ),
            ),
            DigestPaper(make_paper("related")),
        ]

        card = publisher._digest_card(
            "AI",
            papers,
            total_papers=2,
            start_index=1,
        )

        data = card["data"]
        self.assertEqual(data["template_id"], "AAqWNxGgDjV5N")
        variables = data["template_variable"]
        self.assertEqual(len(variables["table_rows"]), 2)
        self.assertEqual(
            variables["paper_list"],
            [
                {
                    "counter": 1,
                    "title": "title recommended",
                    "authors": "Alice, Bob",
                    "evaluation": "一句话摘要",
                }
            ],
        )
        self.assertNotIn("quality_score", str(card))

    def test_raw_digest_contains_recommendation_title_authors_and_summary(
        self,
    ) -> None:
        publisher = self._publisher()
        paper = DigestPaper(
            make_paper("recommended"),
            Recommendation(
                paper_id="recommended",
                summary="一句话摘要",
            ),
        )

        card = publisher._raw_digest_card(
            "AI",
            [paper],
            total_papers=1,
            start_index=1,
        )

        self.assertEqual(card["schema"], "2.0")
        rendered = str(card)
        self.assertIn("title recommended", rendered)
        self.assertIn("Alice, Bob", rendered)
        self.assertIn("一句话摘要", rendered)

    def test_unavailable_template_falls_back_to_raw_digest(self) -> None:
        class FallbackPublisher(LarkPublisher):
            def __init__(self, config):
                super().__init__(config, client=object())
                self.cards = []

            def send_card(self, chat_id, card):
                self.cards.append(card)
                if len(self.cards) == 1:
                    raise LarkPublishError(
                        "template is not visible to app"
                    )

        publisher = FallbackPublisher(self._publisher().config)
        publisher.publish_digest(
            "AI",
            [DigestPaper(make_paper("paper"))],
        )

        self.assertEqual(len(publisher.cards), 2)
        self.assertEqual(publisher.cards[1]["schema"], "2.0")
