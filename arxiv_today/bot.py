"""Long-running Lark command bot for on-demand paper readings."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from typing import Protocol

import lark_oapi as lark
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

from .config import AppConfig
from .lark import LarkPublisher
from .llm import LLMService
from .models import Paper, PaperReading
from .papers import fetch_paper_by_id
from .reading import PaperTextExtractor

READING_PROMPT_VERSION = "reading-v2"
ARXIV_ID_PATTERN = re.compile(
    r"^(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?$",
    flags=re.IGNORECASE,
)
READING_COMMAND_PATTERN = re.compile(r"(?:^|\s)/精读\s+(\S+)")


class ReadingLLM(Protocol):
    def create_reading(
        self,
        paper: Paper,
        *,
        full_text: str | None,
        chunk_characters: int,
    ) -> PaperReading: ...


class ReadingExtractor(Protocol):
    def extract(self, paper: Paper) -> str | None: ...


PaperByIdFetcher = Callable[[str], Paper]


class ReadingCache:
    """Filesystem cache keyed by paper version, model, and prompt version."""

    def __init__(self, directory: str | Path, *, model: str):
        self.directory = Path(directory)
        self.model = model

    def load(self, paper: Paper) -> PaperReading | None:
        path = self._path(paper)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return PaperReading.model_validate(data["reading"])
        except (KeyError, TypeError, ValueError):
            return None

    def store(self, paper: Paper, reading: PaperReading) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self._path(paper)
        payload = {
            "paper_id": paper["id"],
            "paper_version": paper["version"],
            "model": self.model,
            "prompt_version": READING_PROMPT_VERSION,
            "reading": reading.model_dump(),
        }
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=self.directory,
            prefix=f".{path.name}.",
            delete=False,
        ) as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
            temporary_path = Path(file.name)
        os.replace(temporary_path, path)

    def _path(self, paper: Paper) -> Path:
        cache_key = "\0".join(
            (
                paper["version"],
                self.model,
                READING_PROMPT_VERSION,
            )
        )
        digest = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()[:16]
        safe_version = re.sub(r"[^A-Za-z0-9._-]", "_", paper["version"])
        return self.directory / f"{safe_version}-{digest}.json"


class ReadingCommandService:
    """Validates commands and runs one reading generation job at a time."""

    def __init__(
        self,
        config: AppConfig,
        *,
        llm: ReadingLLM | None = None,
        publisher: LarkPublisher | None = None,
        extractor: ReadingExtractor | None = None,
        paper_fetcher: PaperByIdFetcher = fetch_paper_by_id,
        cache: ReadingCache | None = None,
    ):
        self.config = config
        self.llm = llm or LLMService(config.llm)
        self.publisher = publisher or LarkPublisher(config.lark)
        self.extractor = extractor or PaperTextExtractor(
            config.reading.pdf_timeout_seconds
        )
        self.paper_fetcher = paper_fetcher
        self.cache = cache or ReadingCache(
            config.reading_cache_path,
            model=config.llm.effective_reading_model,
        )
        self.executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="paper-reading",
        )
        self._inflight: set[str] = set()
        self._lock = Lock()

    def handle_event(self, event: P2ImMessageReceiveV1) -> None:
        message = event.event.message if event.event else None
        if (
            message is None
            or message.chat_id != self.config.lark.target_chat_id
            or message.message_type != "text"
            or not message.message_id
        ):
            return
        try:
            text = json.loads(message.content or "{}").get("text", "")
        except (TypeError, ValueError):
            return
        match = READING_COMMAND_PATTERN.search(text)
        if not match:
            return
        self.handle_command(message.message_id, match.group(1))

    def handle_command(self, message_id: str, paper_id: str) -> None:
        if not ARXIV_ID_PATTERN.fullmatch(paper_id):
            self.publisher.reply_text(
                message_id,
                "arXiv ID 格式不正确。用法：/精读 2607.27180",
            )
            return

        normalized = paper_id.lower()
        with self._lock:
            if normalized in self._inflight:
                self.publisher.reply_text(
                    message_id,
                    f"{paper_id} 已在生成中，完成后会回复首个请求。",
                )
                return
            self._inflight.add(normalized)

        try:
            self.publisher.reply_text(
                message_id,
                f"正在生成 {paper_id} 的精读，完成后会直接回复。",
            )
        except Exception:
            with self._lock:
                self._inflight.discard(normalized)
            raise
        self.executor.submit(self._generate_and_reply, message_id, paper_id)

    def close(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=False)

    def _generate_and_reply(self, message_id: str, paper_id: str) -> None:
        try:
            paper = self.paper_fetcher(paper_id)
            reading = self.cache.load(paper)
            if reading is None:
                full_text = self.extractor.extract(paper)
                reading = self.llm.create_reading(
                    paper,
                    full_text=full_text,
                    chunk_characters=self.config.reading.chunk_characters,
                )
                self.cache.store(paper, reading)
            self.publisher.reply_reading(message_id, paper, reading)
        except Exception as error:  # noqa: BLE001
            print(f"Reading generation failed for {paper_id}: {error}")
            try:
                self.publisher.reply_text(
                    message_id,
                    "精读生成失败，请稍后重试。",
                )
            except Exception as publish_error:  # noqa: BLE001
                print(f"Failed to report reading error to Lark: {publish_error}")
        finally:
            with self._lock:
                self._inflight.discard(paper_id.lower())


def run_bot(config: AppConfig) -> None:
    """Start the Lark long-connection client and block forever."""
    service = ReadingCommandService(config)
    event_handler = (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(service.handle_event)
        .build()
    )
    client = lark.ws.Client(
        config.lark.app_id,
        config.lark.app_secret,
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO,
    )
    try:
        client.start()
    finally:
        service.close()
