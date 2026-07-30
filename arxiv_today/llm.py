"""OpenAI-compatible LLM client and paper-specific operations."""

from __future__ import annotations

import re

from openai import OpenAI

from .config import LLMConfig
from .models import Paper
from .prompts import abstract_translation_prompt, paper_match_prompt


class LLMService:
    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = OpenAI(
            api_key=config.effective_api_key,
            base_url=config.base_url,
        )

    def complete(self, prompt: str) -> str | None:
        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[{"role": "user", "content": prompt}],
                stream=False,
            )
            content = response.choices[0].message.content
            return content.strip() if content else None
        # SDKs and OpenAI-compatible servers can surface several exception
        # families; this boundary deliberately converts all of them to None.
        except Exception as error:  # noqa: BLE001
            print(f"LLM Server Error: {error}")
            return None

    def matches(self, paper: Paper, criteria: str) -> bool:
        response = self.complete(
            paper_match_prompt(paper["title"], paper["abstract"], criteria)
        )
        if not response:
            # Preserve the previous fail-open behavior.
            print(
                f"LLM Service Error for paper: {paper['title']}. Assuming it matches."
            )
            return True
        answer = self._remove_thinking(response)
        print(f'LLM response for paper "{paper["title"]}": {answer}')
        return "yes" in answer.lower()

    def translate(self, abstract: str) -> str | None:
        response = self.complete(abstract_translation_prompt(abstract))
        return self._remove_thinking(response) if response else None

    @staticmethod
    def _remove_thinking(text: str) -> str:
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
