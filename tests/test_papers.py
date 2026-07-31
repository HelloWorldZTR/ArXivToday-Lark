import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

import arxiv

from arxiv_today.models import Paper
from arxiv_today.papers import SeenPaperStore, _results_with_backoff


class ArxivBackoffTest(TestCase):
    @mock.patch("arxiv_today.papers.time.sleep")
    @mock.patch("arxiv_today.papers.arxiv.Client")
    def test_retries_429_with_exponential_delays(
        self,
        client_class: mock.Mock,
        sleep: mock.Mock,
    ) -> None:
        client = client_class.return_value
        client.results.side_effect = [
            arxiv.HTTPError("url", 0, 429),
            arxiv.HTTPError("url", 0, 429),
            ["paper"],
        ]

        results = _results_with_backoff(arxiv.Search(id_list=["2607.00001"]))

        self.assertEqual(results, ["paper"])
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [15.0, 30.0])
        self.assertEqual(client_class.call_args_list, [mock.call(num_retries=0)] * 3)

    @mock.patch("arxiv_today.papers.time.sleep")
    @mock.patch("arxiv_today.papers.arxiv.Client")
    def test_does_not_retry_non_transient_http_errors(
        self,
        client_class: mock.Mock,
        sleep: mock.Mock,
    ) -> None:
        client_class.return_value.results.side_effect = arxiv.HTTPError(
            "url",
            0,
            400,
        )

        with self.assertRaises(arxiv.HTTPError):
            _results_with_backoff(arxiv.Search(id_list=["bad-id"]))

        sleep.assert_not_called()


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
                    "version": "legacy-idv1",
                },
                {
                    "id": "new-id",
                    "title": "new",
                    "abstract": "b",
                    "authors": ("B",),
                    "url": "url",
                    "published": "2026-01-02",
                    "version": "new-idv1",
                },
            ]

            self.assertEqual(
                [paper["id"] for paper in store.exclude_seen(papers)],
                ["new-id"],
            )
            self.assertEqual(store.baseline_date, "2026-01-01")
            store.commit(["new-id"])
            self.assertEqual(store.read_ids(), {"legacy-id", "new-id"})
