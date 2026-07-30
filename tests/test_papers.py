import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from arxiv_today.models import Paper
from arxiv_today.papers import SeenPaperStore


class SeenPaperStoreTest(TestCase):
    def test_imports_legacy_ids_and_commits_atomically(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / "papers.json"
            legacy.write_text(
                json.dumps(
                    [
                        {
                            "id": "legacy-id",
                            "title": "old",
                            "published": "2026-01-01",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            store = SeenPaperStore(
                root / "seen.json",
                legacy_history_path=legacy,
            )
            papers: list[Paper] = [
                {
                    "id": "legacy-id",
                    "title": "old",
                    "abstract": "a",
                    "authors": ("A",),
                    "url": "url",
                    "published": "2026-01-01",
                },
                {
                    "id": "new-id",
                    "title": "new",
                    "abstract": "b",
                    "authors": ("B",),
                    "url": "url",
                    "published": "2026-01-02",
                },
            ]

            self.assertEqual(
                [paper["id"] for paper in store.exclude_seen(papers)],
                ["new-id"],
            )
            self.assertEqual(store.baseline_date, "2026-01-01")
            store.commit(["new-id"])
            self.assertEqual(store.read_ids(), {"legacy-id", "new-id"})
