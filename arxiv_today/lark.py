"""Lark webhook publisher for digest and reading cards."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import requests

from .config import LarkConfig
from .models import EvaluatedPaper, PaperReading


class LarkPublishError(RuntimeError):
    """Raised when Lark rejects a card."""


class LarkPublisher:
    def __init__(self, config: LarkConfig):
        self.config = config

    def publish_digest(self, tag: str, papers: list[EvaluatedPaper]) -> None:
        batch_size = self.config.main_card_batch_size
        batches = [
            papers[index : index + batch_size]
            for index in range(0, len(papers), batch_size)
        ] or [[]]
        for batch_index, batch in enumerate(batches):
            self._post(
                self._digest_payload(
                    tag,
                    batch,
                    total_papers=len(papers),
                    start_index=batch_index * batch_size + 1,
                )
            )

    def publish_reading(
        self,
        evaluated: EvaluatedPaper,
        reading: PaperReading,
    ) -> None:
        self._post(self._reading_payload(evaluated, reading))

    def _post(self, payload: dict[str, Any]) -> None:
        try:
            response = requests.post(
                self.config.webhook_url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=30,
            )
        except requests.RequestException as error:
            raise LarkPublishError(f"Lark request failed: {error}") from error
        if response.status_code != 200:
            raise LarkPublishError(
                f"Lark returned HTTP {response.status_code}: {response.text}"
            )
        try:
            body = response.json()
        except ValueError as error:
            raise LarkPublishError("Lark returned invalid JSON") from error
        code = body.get("code", body.get("StatusCode", 0))
        if code not in (0, None):
            raise LarkPublishError(f"Lark rejected the card: {body}")
        print(f"Lark request successful: {body}")

    def _digest_payload(
        self,
        tag: str,
        papers: list[EvaluatedPaper],
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
        evaluations = [
            {
                "counter": index,
                "quality_score": item.quality_label,
                "evaluation": item.one_sentence,
            }
            for index, item in enumerate(papers, start=start_index)
        ]
        if not self.config.template_id or not self.config.template_version_name:
            raise LarkPublishError(
                "Digest template_id and template_version_name are required"
            )
        return {
            "msg_type": "interactive",
            "card": {
                "type": "template",
                "data": {
                    "template_id": self.config.template_id,
                    "template_version_name": self.config.template_version_name,
                    "template_variable": {
                        "today_date": datetime.now().astimezone().date().isoformat(),
                        "tag": tag,
                        "total_paper": total_papers,
                        "table_rows": table_rows,
                        "paper_list": evaluations,
                    },
                },
            },
        }

    def _reading_payload(
        self,
        evaluated: EvaluatedPaper,
        reading: PaperReading,
    ) -> dict[str, Any]:
        paper = evaluated.paper
        source_labels = {
            "full_text": "PDF 全文",
            "abstract_fallback": "摘要降级版",
            "generation_failed": "精读生成失败",
        }
        quality_score = evaluated.quality_label
        authors = ", ".join(paper["authors"]) or "Unknown"
        return {
            "msg_type": "interactive",
            "card": {
                "schema": "2.0",
                "config": {"update_multi": True},
                "header": {
                    "title": {"tag": "plain_text", "content": paper["title"]},
                    "subtitle": {
                        "tag": "plain_text",
                        "content": f"Quality {quality_score}/100",
                    },
                    "template": "blue",
                },
                "body": {
                    "elements": [
                        {
                            "tag": "markdown",
                            "content": (
                                f"**作者**：{authors}\n\n"
                                f"**一句话评价**：{evaluated.one_sentence}\n\n"
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
            },
        }
