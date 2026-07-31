"""Lark application-bot publisher for digest and reading cards."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    ReplyMessageRequest,
    ReplyMessageRequestBody,
)

from .config import LarkConfig
from .models import DigestPaper, Paper, PaperReading


class LarkPublishError(RuntimeError):
    """Raised when Lark rejects a message."""


class LarkPublisher:
    def __init__(self, config: LarkConfig, *, client: Any | None = None):
        self.config = config
        self.client = client or (
            lark.Client.builder()
            .app_id(config.app_id)
            .app_secret(config.app_secret)
            .log_level(lark.LogLevel.ERROR)
            .build()
        )

    def publish_digest(self, tag: str, papers: list[DigestPaper]) -> None:
        batch_size = self.config.main_card_batch_size
        batches = [
            papers[index : index + batch_size]
            for index in range(0, len(papers), batch_size)
        ] or [[]]
        for batch_index, batch in enumerate(batches):
            start_index = batch_index * batch_size + 1
            template_card = self._digest_card(
                tag,
                batch,
                total_papers=len(papers),
                start_index=start_index,
            )
            try:
                self.send_card(self.config.target_chat_id, template_card)
            except LarkPublishError as error:
                if "template is not visible to app" not in str(error):
                    raise
                print(
                    "Digest template is unavailable to this app; "
                    "falling back to a raw Card 2.0 digest."
                )
                self.send_card(
                    self.config.target_chat_id,
                    self._raw_digest_card(
                        tag,
                        batch,
                        total_papers=len(papers),
                        start_index=start_index,
                    ),
                )

    def send_text(self, chat_id: str, content: str) -> None:
        self._create_message(chat_id, "text", {"text": content})

    def reply_text(self, message_id: str, content: str) -> None:
        self._reply_message(message_id, "text", {"text": content})

    def send_card(self, chat_id: str, card: dict[str, Any]) -> None:
        self._create_message(chat_id, "interactive", card)

    def reply_reading(
        self,
        message_id: str,
        paper: Paper,
        reading: PaperReading,
    ) -> None:
        self._reply_message(
            message_id,
            "interactive",
            self._reading_card(paper, reading),
        )

    def _create_message(
        self,
        chat_id: str,
        msg_type: str,
        content: dict[str, Any],
    ) -> None:
        request = (
            CreateMessageRequest.builder()
            .receive_id_type("chat_id")
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(chat_id)
                .msg_type(msg_type)
                .content(json.dumps(content, ensure_ascii=False))
                .build()
            )
            .build()
        )
        response = self.client.im.v1.message.create(request)
        self._validate_response(response)

    def _reply_message(
        self,
        message_id: str,
        msg_type: str,
        content: dict[str, Any],
    ) -> None:
        request = (
            ReplyMessageRequest.builder()
            .message_id(message_id)
            .request_body(
                ReplyMessageRequestBody.builder()
                .msg_type(msg_type)
                .content(json.dumps(content, ensure_ascii=False))
                .build()
            )
            .build()
        )
        response = self.client.im.v1.message.reply(request)
        self._validate_response(response)

    @staticmethod
    def _validate_response(response: Any) -> None:
        if response.success():
            return
        raise LarkPublishError(
            f"Lark rejected message: code={response.code}, "
            f"message={response.msg}, log_id={response.get_log_id()}"
        )

    def _digest_card(
        self,
        tag: str,
        papers: list[DigestPaper],
        *,
        total_papers: int,
        start_index: int,
    ) -> dict[str, Any]:
        table_rows = [
            {
                "index": index,
                "paper": (
                    f"**[{item.paper['title']}]({item.paper['url']})**\n"
                    f"<text_tag color='grey'>arXiv: {item.paper['id']}</text_tag>"
                ),
                "published": item.paper["published"],
            }
            for index, item in enumerate(papers, start=start_index)
        ]
        recommendations = [
            {
                "counter": index,
                "title": item.paper["title"],
                "authors": ", ".join(item.paper["authors"]) or "Unknown",
                "evaluation": item.recommendation.summary,
            }
            for index, item in enumerate(papers, start=start_index)
            if item.recommendation is not None
        ]
        if not self.config.template_id or not self.config.template_version_name:
            raise LarkPublishError(
                "Digest template_id and template_version_name are required"
            )
        return {
            "type": "template",
            "data": {
                "template_id": self.config.template_id,
                "template_version_name": self.config.template_version_name,
                "template_variable": {
                    "today_date": datetime.now().astimezone().date().isoformat(),
                    "tag": tag,
                    "total_paper": total_papers,
                    "table_rows": table_rows,
                    "paper_list": recommendations,
                },
            },
        }

    def _reading_card(
        self,
        paper: Paper,
        reading: PaperReading,
    ) -> dict[str, Any]:
        source_labels = {
            "full_text": "PDF 全文",
            "abstract_fallback": "摘要降级版",
        }
        authors = ", ".join(paper["authors"]) or "Unknown"
        return {
            "schema": "2.0",
            "config": {"update_multi": True},
            "header": {
                "title": {"tag": "plain_text", "content": paper["title"]},
                "subtitle": {
                    "tag": "plain_text",
                    "content": f"按需精读 · {source_labels[reading.source]}",
                },
                "template": "blue",
            },
            "body": {
                "elements": [
                    {
                        "tag": "markdown",
                        "content": (
                            f"**作者**：{authors}\n\n"
                            f"**来源**：{source_labels[reading.source]}\n\n"
                            f"[打开论文]({paper['url']})"
                        ),
                    },
                    {
                        "tag": "collapsible_panel",
                        "expanded": False,
                        "header": {
                            "title": {
                                "tag": "plain_text",
                                "content": "展开论文精读",
                            }
                        },
                        "elements": [
                            {
                                "tag": "markdown",
                                "content": reading.content,
                            }
                        ],
                    },
                ]
            },
        }

    def _raw_digest_card(
        self,
        tag: str,
        papers: list[DigestPaper],
        *,
        total_papers: int,
        start_index: int,
    ) -> dict[str, Any]:
        rows = [
            {
                "index": index,
                "paper": (
                    f"**[{item.paper['title']}]({item.paper['url']})**\n"
                    f"<text_tag color='grey'>arXiv: {item.paper['id']}</text_tag>"
                ),
                "published": item.paper["published"],
            }
            for index, item in enumerate(papers, start=start_index)
        ]
        elements: list[dict[str, Any]] = [
            {
                "tag": "markdown",
                "content": (
                    "ArXiv Today 小助手来啦٩(๑˃̵ᴗ˂̵๑)۶\n"
                    f"今日找到了**{total_papers}**篇相关论文(..＞◡＜..)"
                ),
            },
            {
                "tag": "table",
                "page_size": 5,
                "row_height": "middle",
                "header_style": {
                    "background_style": "grey",
                    "bold": True,
                    "lines": 1,
                },
                "columns": [
                    {
                        "data_type": "number",
                        "name": "index",
                        "display_name": "序号",
                        "horizontal_align": "center",
                        "width": "auto",
                    },
                    {
                        "data_type": "lark_md",
                        "name": "paper",
                        "display_name": "论文",
                        "horizontal_align": "left",
                        "width": "auto",
                    },
                    {
                        "data_type": "text",
                        "name": "published",
                        "display_name": "论文日期",
                        "horizontal_align": "center",
                        "width": "auto",
                    },
                ],
                "rows": rows,
            },
        ]
        for index, item in enumerate(papers, start=start_index):
            if item.recommendation is None:
                continue
            authors = ", ".join(item.paper["authors"]) or "Unknown"
            elements.extend(
                [
                    {
                        "tag": "markdown",
                        "content": (
                            f"### {index}. 推荐｜"
                            f"[{item.paper['title']}]({item.paper['url']})"
                        ),
                    },
                    {
                        "tag": "markdown",
                        "content": (
                            f"**作者**：{authors}\n\n"
                            f"{item.recommendation.summary}"
                        ),
                    },
                    {"tag": "hr"},
                ]
            )
        return {
            "schema": "2.0",
            "config": {"update_multi": True},
            "header": {
                "title": {"tag": "plain_text", "content": "ArXiv Today"},
                "subtitle": {
                    "tag": "plain_text",
                    "content": datetime.now().astimezone().date().isoformat(),
                },
                "text_tag_list": [
                    {
                        "tag": "text_tag",
                        "text": {"tag": "plain_text", "content": tag},
                        "color": "purple",
                    }
                ],
                "template": "wathet",
                "ud_icon": {
                    "tag": "standard_icon",
                    "token": "send_outlined",
                },
            },
            "body": {"elements": elements},
        }
