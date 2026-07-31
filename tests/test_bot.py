import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from unittest import TestCase

from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

from arxiv_today.bot import ReadingCache, ReadingCommandService
from arxiv_today.config import (
    AppConfig,
    LarkConfig,
    LLMConfig,
    PaperConfig,
)
from arxiv_today.models import Paper, PaperReading
from tests.test_pipeline import make_paper


class FakePublisher:
    def __init__(self):
        self.text_replies: list[tuple[str, str]] = []
        self.reading_replies: list[tuple[str, Paper, PaperReading]] = []

    def reply_text(self, message_id: str, content: str) -> None:
        self.text_replies.append((message_id, content))

    def reply_reading(
        self,
        message_id: str,
        paper: Paper,
        reading: PaperReading,
    ) -> None:
        self.reading_replies.append((message_id, paper, reading))


class FakeLLM:
    def __init__(self):
        self.calls = 0

    def create_reading(
        self,
        paper: Paper,
        *,
        full_text: str | None,
        chunk_characters: int,
    ) -> PaperReading:
        self.calls += 1
        source = "full_text" if full_text else "abstract_fallback"
        return PaperReading(content=f"reading {paper['id']}", source=source)


class BlockingLLM(FakeLLM):
    def __init__(self):
        super().__init__()
        self.started = Event()
        self.release = Event()

    def create_reading(
        self,
        paper: Paper,
        *,
        full_text: str | None,
        chunk_characters: int,
    ) -> PaperReading:
        self.started.set()
        self.release.wait(timeout=2)
        return super().create_reading(
            paper,
            full_text=full_text,
            chunk_characters=chunk_characters,
        )


class FakeExtractor:
    def __init__(self, result: str | None = "full text"):
        self.result = result
        self.calls = 0

    def extract(self, paper: Paper) -> str | None:
        self.calls += 1
        return self.result


def make_config(root: Path) -> AppConfig:
    return AppConfig(
        lark=LarkConfig(
            app_id="app",
            app_secret="secret",
            target_chat_id="allowed-chat",
            template_id="template",
            template_version_name="1.0.0",
        ),
        paper=PaperConfig(tag="AI", categories=("cs.AI",)),
        llm=LLMConfig(
            model="model",
            reading_model="reading-model",
            base_url="https://api.example/v1",
            api_key="key",
        ),
        base_dir=root,
    )


def message_event(
    *,
    chat_id: str,
    message_id: str = "message",
    text: str = "/精读 2607.27180",
) -> P2ImMessageReceiveV1:
    return P2ImMessageReceiveV1(
        {
            "event": {
                "message": {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "message_type": "text",
                    "content": json.dumps({"text": text}),
                }
            }
        }
    )


class ReadingCommandServiceTest(TestCase):
    def test_ignores_commands_from_other_chats(self) -> None:
        with TemporaryDirectory() as directory:
            publisher = FakePublisher()
            service = ReadingCommandService(
                make_config(Path(directory)),
                llm=FakeLLM(),
                publisher=publisher,  # type: ignore[arg-type]
                extractor=FakeExtractor(),
            )

            service.handle_event(message_event(chat_id="other-chat"))
            service.close()

            self.assertEqual(publisher.text_replies, [])

    def test_invalid_arxiv_id_returns_usage_without_starting_job(self) -> None:
        with TemporaryDirectory() as directory:
            publisher = FakePublisher()
            llm = FakeLLM()
            service = ReadingCommandService(
                make_config(Path(directory)),
                llm=llm,
                publisher=publisher,  # type: ignore[arg-type]
                extractor=FakeExtractor(),
            )

            service.handle_command("message", "not-an-id")
            service.close()

            self.assertIn("格式不正确", publisher.text_replies[0][1])
            self.assertEqual(llm.calls, 0)

    def test_command_acknowledges_and_replies_with_reading(self) -> None:
        with TemporaryDirectory() as directory:
            publisher = FakePublisher()
            llm = FakeLLM()
            service = ReadingCommandService(
                make_config(Path(directory)),
                llm=llm,
                publisher=publisher,  # type: ignore[arg-type]
                extractor=FakeExtractor(),
                paper_fetcher=lambda _paper_id: make_paper("2607.27180"),
            )

            service.handle_command("message", "2607.27180")
            service.executor.shutdown(wait=True)

            self.assertIn("正在生成", publisher.text_replies[0][1])
            self.assertEqual(len(publisher.reading_replies), 1)
            self.assertEqual(llm.calls, 1)

    def test_cached_reading_skips_extraction_and_llm(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            paper = make_paper("2607.27180")
            cache = ReadingCache(root / "cache", model="reading-model")
            cache.store(
                paper,
                PaperReading(content="cached", source="full_text"),
            )
            publisher = FakePublisher()
            llm = FakeLLM()
            extractor = FakeExtractor()
            service = ReadingCommandService(
                make_config(root),
                llm=llm,
                publisher=publisher,  # type: ignore[arg-type]
                extractor=extractor,
                paper_fetcher=lambda _paper_id: paper,
                cache=cache,
            )

            service.handle_command("message", "2607.27180")
            service.executor.shutdown(wait=True)

            self.assertEqual(llm.calls, 0)
            self.assertEqual(extractor.calls, 0)
            self.assertEqual(
                publisher.reading_replies[0][2].content,
                "cached",
            )

    def test_concurrent_duplicate_reuses_the_inflight_job(self) -> None:
        with TemporaryDirectory() as directory:
            publisher = FakePublisher()
            llm = BlockingLLM()
            service = ReadingCommandService(
                make_config(Path(directory)),
                llm=llm,
                publisher=publisher,  # type: ignore[arg-type]
                extractor=FakeExtractor(),
                paper_fetcher=lambda _paper_id: make_paper("2607.27180"),
            )

            service.handle_command("first", "2607.27180")
            self.assertTrue(llm.started.wait(timeout=1))
            service.handle_command("second", "2607.27180")
            llm.release.set()
            service.executor.shutdown(wait=True)

            self.assertEqual(llm.calls, 1)
            self.assertIn("已在生成中", publisher.text_replies[1][1])
            self.assertEqual(len(publisher.reading_replies), 1)

    def test_pdf_failure_generates_labeled_abstract_fallback(self) -> None:
        with TemporaryDirectory() as directory:
            publisher = FakePublisher()
            service = ReadingCommandService(
                make_config(Path(directory)),
                llm=FakeLLM(),
                publisher=publisher,  # type: ignore[arg-type]
                extractor=FakeExtractor(None),
                paper_fetcher=lambda _paper_id: make_paper("2607.27180"),
            )

            service.handle_command("message", "2607.27180")
            service.executor.shutdown(wait=True)

            self.assertEqual(
                publisher.reading_replies[0][2].source,
                "abstract_fallback",
            )
