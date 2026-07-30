"""Download and extract arXiv paper text."""

from __future__ import annotations

from io import BytesIO

import requests
from pypdf import PdfReader

from .models import Paper


class PaperTextExtractor:
    def __init__(self, timeout_seconds: int = 30):
        self.timeout_seconds = timeout_seconds

    def extract(self, paper: Paper) -> str | None:
        pdf_url = f"https://arxiv.org/pdf/{paper['id']}.pdf"
        try:
            response = requests.get(pdf_url, timeout=self.timeout_seconds)
            response.raise_for_status()
            reader = PdfReader(BytesIO(response.content))
            text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
            return text.strip() or None
        except Exception as error:  # noqa: BLE001
            print(f'PDF extraction failed for "{paper["title"]}": {error}')
            return None
