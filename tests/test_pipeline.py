from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from arxiv_today.config import (
    AppConfig,
    LarkConfig,
    LLMConfig,
    PaperConfig,
    QualityConfig,
    ReadingConfig,
)
from arxiv_today.lark import LarkPublishError
from arxiv_today.models import (
    EvaluatedPaper,
    Paper,
    PaperReading,
    QualityAssessment,
)
from arxiv_today.papers import SeenPaperStore
from arxiv_today.pipeline import PaperPipeline


def quality(score: int) -> QualityAssessment:
    novelty = min(score, 25)
    technical = min(max(score - novelty, 0), 25)
    experimental = min(max(score - novelty - technical, 0), 20)
    impact = min(max(score - novelty - technical - experimental, 0), 20)
    author = score - novelty - technical - experimental - impact
    return QualityAssessment(
        novelty=novelty,
        technical_depth=technical,
        experimental_credibility=experimental,
        potential_impact=impact,
        author_signal=author,
        total=score,
        one_sentence=f"quality {score}",
        reason="test",
        is_important=score >= 75,
    )


class FakeLLM:
    def __init__(self, scores: dict[str, int | None]):
        self.scores = scores
        self.reading_inputs: list[tuple[str, str | None]] = []

    def matches(self, paper: Paper, criteria: str) -> bool:
        return paper["id"] != "unrelated" and criteria == "target"

    def assess_quality(
        self, paper: Paper, *, threshold: int
    ) -> QualityAssessment | None:
        score = self.scores[paper["id"]]
        return quality(score) if score is not None else None

    def create_reading(
        self,
        paper: Paper,
        *,
        full_text: str | None,
        chunk_characters: int,
    ) -> PaperReading:
        self.reading_inputs.append((paper["id"], full_text))
        source = "full_text" if full_text else "abstract_fallback"
        return PaperReading(content=f"reading {paper['id']}", source=source)


class FakePublisher:
    def __init__(self, *, fail_digest: bool = False, fail_first_reading: bool = False):
        self.fail_digest = fail_digest
        self.fail_first_reading = fail_first_reading
        self.digest: list[EvaluatedPaper] | None = None
        self.reading_attempts: list[str] = []

    def publish_digest(self, tag: str, papers: list[EvaluatedPaper]) -> None:
        if self.fail_digest:
            raise LarkPublishError("digest failed")
        self.digest = papers

    def publish_reading(self, evaluated: EvaluatedPaper, reading: PaperReading) -> None:
        self.reading_attempts.append(evaluated.paper["id"])
        if self.fail_first_reading and len(self.reading_attempts) == 1:
            raise LarkPublishError("reading failed")


class FakeExtractor:
    def extract(self, paper: Paper) -> str | None:
        return None if paper["id"] == "fallback" else f"full {paper['id']}"


def make_paper(paper_id: str) -> Paper:
    return {
        "id": paper_id,
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
                webhook_url="url",
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
                base_url="http://localhost/v1",
                api_key="key",
            ),
            quality=QualityConfig(
                threshold=75,
                max_readings_per_run=2,
            ),
            reading=ReadingConfig(),
            base_dir=root,
        )

    def test_all_related_are_in_digest_and_readings_are_ranked_and_limited(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "criteria.md").write_text("target", encoding="utf-8")
            papers = [
                make_paper("low"),
                make_paper("high"),
                make_paper("fallback"),
                make_paper("quality-failed"),
                make_paper("unrelated"),
            ]
            scores = {
                "low": 60,
                "high": 95,
                "fallback": 85,
                "quality-failed": None,
                "unrelated": 90,
            }
            llm = FakeLLM(scores)
            publisher = FakePublisher(fail_first_reading=True)
            store = SeenPaperStore(root / "seen.json")
            store.initialize("2025-12-31")
            pipeline = PaperPipeline(
                self._config(root),
                fetcher=lambda _category, _limit: papers,
                llm=llm,
                publisher=publisher,
                seen_store=store,
                text_extractor=FakeExtractor(),
            )

            result = pipeline.run()

            self.assertEqual(
                [item.paper["id"] for item in result],
                ["low", "high", "fallback", "quality-failed"],
            )
            self.assertEqual(publisher.digest, result)
            self.assertEqual(
                publisher.reading_attempts,
                ["high", "fallback"],
            )
            self.assertEqual(
                llm.reading_inputs,
                [("high", "full high"), ("fallback", None)],
            )
            self.assertEqual(
                store.read_ids(),
                {"low", "high", "fallback", "quality-failed", "unrelated"},
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
                llm=FakeLLM({"new": 80}),
                publisher=FakePublisher(fail_digest=True),
                seen_store=store,
                text_extractor=FakeExtractor(),
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
                llm=FakeLLM({"existing": 90}),
                publisher=publisher,
                seen_store=store,
                text_extractor=FakeExtractor(),
            )

            result = pipeline.run()

            self.assertEqual(result, [])
            self.assertIsNone(publisher.digest)
            self.assertIsNotNone(store.baseline_date)
