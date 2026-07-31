from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from arxiv_today.config import (
    AppConfig,
    LarkConfig,
    LLMConfig,
    PaperConfig,
    ReadingConfig,
    RecommendationConfig,
)
from arxiv_today.lark import LarkPublishError
from arxiv_today.models import DigestPaper, Paper, Recommendation, Relevance
from arxiv_today.papers import SeenPaperStore
from arxiv_today.pipeline import PaperPipeline


class FakeLLM:
    def __init__(
        self,
        relevance: dict[str, Relevance],
        recommendation_ids: list[str],
    ):
        self.relevance = relevance
        self.recommendation_ids = recommendation_ids
        self.classification_batch_size: int | None = None
        self.selection_batch_size: int | None = None

    def classify_related(
        self,
        papers: list[Paper],
        criteria: str,
        *,
        batch_size: int,
    ) -> dict[str, Relevance]:
        assert criteria == "target"
        self.classification_batch_size = batch_size
        return {paper["id"]: self.relevance[paper["id"]] for paper in papers}

    def select_recommendations(
        self,
        papers: list[Paper],
        criteria: str,
        *,
        limit: int,
        batch_size: int,
    ) -> list[Recommendation]:
        assert criteria == "target"
        self.selection_batch_size = batch_size
        available = {paper["id"] for paper in papers}
        return [
            Recommendation(paper_id=paper_id, summary=f"summary {paper_id}")
            for paper_id in self.recommendation_ids[:limit]
            if paper_id in available
        ]


class FakePublisher:
    def __init__(self, *, fail_digest: bool = False):
        self.fail_digest = fail_digest
        self.digest: list[DigestPaper] | None = None

    def publish_digest(self, tag: str, papers: list[DigestPaper]) -> None:
        if self.fail_digest:
            raise LarkPublishError("digest failed")
        self.digest = papers


def make_paper(paper_id: str) -> Paper:
    return {
        "id": paper_id,
        "version": f"{paper_id}v1",
        "title": f"title {paper_id}",
        "abstract": "an abstract without configured keywords",
        "authors": ("Alice", "Bob"),
        "url": f"https://arxiv.org/abs/{paper_id}",
        "published": "2026-01-01",
    }


class PaperPipelineTest(TestCase):
    def _config(self, root: Path) -> AppConfig:
        return AppConfig(
            lark=LarkConfig(
                app_id="app",
                app_secret="secret",
                target_chat_id="chat",
                template_id="template",
                template_version_name="1.0.0",
            ),
            paper=PaperConfig(
                tag="AI",
                categories=("cs.AI",),
                criteria_file="criteria.md",
            ),
            llm=LLMConfig(
                model="model",
                base_url="https://api.example/v1",
                api_key="key",
            ),
            recommendation=RecommendationConfig(
                related_batch_size=10,
                selection_batch_size=30,
                max_recommendations=5,
            ),
            reading=ReadingConfig(),
            base_dir=root,
        )

    def test_digest_contains_recommendations_then_related_and_hides_possible(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "criteria.md").write_text("target", encoding="utf-8")
            papers = [
                make_paper("related-1"),
                make_paper("possible-recommended"),
                make_paper("possible-hidden"),
                make_paper("related-2"),
                make_paper("unrelated"),
            ]
            llm = FakeLLM(
                {
                    "related-1": "related",
                    "possible-recommended": "possible",
                    "possible-hidden": "possible",
                    "related-2": "related",
                    "unrelated": "unrelated",
                },
                ["possible-recommended", "related-2"],
            )
            publisher = FakePublisher()
            store = SeenPaperStore(root / "seen.json")
            store.initialize("2025-12-31")
            pipeline = PaperPipeline(
                self._config(root),
                fetcher=lambda _category, _limit: papers,
                llm=llm,
                publisher=publisher,
                seen_store=store,
            )

            result = pipeline.run()

            self.assertEqual(
                [item.paper["id"] for item in result],
                ["possible-recommended", "related-2", "related-1"],
            )
            self.assertEqual(
                [item.paper["id"] for item in result if item.recommendation],
                ["possible-recommended", "related-2"],
            )
            self.assertEqual(publisher.digest, result)
            self.assertEqual(llm.classification_batch_size, 10)
            self.assertEqual(llm.selection_batch_size, 30)
            self.assertEqual(
                store.read_ids(),
                {paper["id"] for paper in papers},
            )

    def test_digest_failure_does_not_commit_seen_state(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "criteria.md").write_text("target", encoding="utf-8")
            paper = make_paper("new")
            store = SeenPaperStore(root / "seen.json")
            store.initialize("2025-12-31")
            pipeline = PaperPipeline(
                self._config(root),
                fetcher=lambda _category, _limit: [paper],
                llm=FakeLLM({"new": "related"}, []),
                publisher=FakePublisher(fail_digest=True),
                seen_store=store,
            )

            with self.assertRaises(LarkPublishError):
                pipeline.run()

            self.assertEqual(store.read_ids(), set())

    def test_first_run_only_initializes_date_baseline(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "criteria.md").write_text("target", encoding="utf-8")
            publisher = FakePublisher()
            store = SeenPaperStore(root / "seen.json")
            pipeline = PaperPipeline(
                self._config(root),
                fetcher=lambda _category, _limit: [make_paper("existing")],
                llm=FakeLLM({"existing": "related"}, ["existing"]),
                publisher=publisher,
                seen_store=store,
            )

            result = pipeline.run()

            self.assertEqual(result, [])
            self.assertIsNone(publisher.digest)
            self.assertIsNotNone(store.baseline_date)
