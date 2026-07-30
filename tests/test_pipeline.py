from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from arxiv_today.config import (
    AppConfig,
    FeatureConfig,
    LarkConfig,
    LLMConfig,
    PaperConfig,
)
from arxiv_today.models import Paper
from arxiv_today.papers import PaperHistory
from arxiv_today.pipeline import PaperPipeline


class FakeLLM:
    def matches(self, paper: Paper, criteria: str) -> bool:
        return "wanted" in paper["title"] and criteria == "target"

    def translate(self, abstract: str) -> str:
        return f"中文：{abstract}"


class FakePublisher:
    def __init__(self) -> None:
        self.published: tuple[str, list[Paper]] | None = None

    def publish(self, tag: str, papers: list[Paper]) -> None:
        self.published = (tag, papers)


class PaperPipelineTest(TestCase):
    def test_pipeline_owns_the_full_workflow(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "criteria.md").write_text("target", encoding="utf-8")
            config = AppConfig(
                lark=LarkConfig(
                    webhook_url="url",
                    template_id="template",
                    template_version_name="1.0.0",
                ),
                paper=PaperConfig(
                    tag="AI",
                    categories=("cs.AI", "cs.CL"),
                    keywords=("safety",),
                    criteria_file="criteria.md",
                ),
                llm=LLMConfig(
                    model="model",
                    base_url="http://localhost/v1",
                    api_key="key",
                ),
                features=FeatureConfig(
                    llm_filtering=True,
                    llm_translation=True,
                ),
                base_dir=root,
            )
            paper: Paper = {
                "id": "1",
                "title": "wanted paper",
                "abstract": "safety research",
                "url": "https://arxiv.org/abs/1",
                "published": "2026-01-01",
            }

            def fetcher(category: str, max_results: int) -> list[Paper]:
                self.assertEqual(max_results, 100)
                return [paper.copy()]

            publisher = FakePublisher()
            pipeline = PaperPipeline(
                config,
                fetcher=fetcher,
                llm=FakeLLM(),  # type: ignore[arg-type]
                publisher=publisher,  # type: ignore[arg-type]
                history=PaperHistory(root / "history.json"),
            )

            result = pipeline.run()

            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].get("zh_abstract"), "中文：safety research")
            self.assertEqual(publisher.published, ("AI", result))
            self.assertEqual(
                PaperHistory(root / "history.json").exclude_seen(result), []
            )
