"""Lark webhook publisher."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import requests

from .config import LarkConfig
from .models import Paper


class LarkPublisher:
    def __init__(self, config: LarkConfig):
        self.config = config

    def publish(self, tag: str, papers: list[Paper]) -> None:
        response = requests.post(
            self.config.webhook_url,
            headers={"Content-Type": "application/json"},
            json=self._payload(tag, papers),
            timeout=30,
        )
        if response.status_code == 200:
            print("Request successful")
            print(f"Response:\n{response.json()}")
        else:
            print(f"Request failed, status code: {response.status_code}")
            print(f"Response:\n{response.text}")

    def _payload(self, tag: str, papers: list[Paper]) -> dict[str, Any]:
        table_rows = [
            {
                "index": index,
                "title": paper["title"],
                "id": paper["id"],
                "published": paper["published"],
                "url": f"[{paper['url']}]({paper['url']})",
            }
            for index, paper in enumerate(papers, start=1)
        ]
        paper_list = [
            {
                "counter": index,
                "title": paper["title"],
                "id": paper["id"],
                "abstract": paper["abstract"],
                "zh_abstract": paper.get("zh_abstract"),
                "url": paper["url"],
                "published": paper["published"],
            }
            for index, paper in enumerate(papers, start=1)
        ]
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
                        "total_paper": len(papers),
                        "table_rows": table_rows,
                        "paper_list": paper_list,
                    },
                },
            },
        }
