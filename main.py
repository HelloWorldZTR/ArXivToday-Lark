"""Command-line entry points for the digest and long-running Lark bot."""

import argparse

from arxiv_today import AppConfig, PaperPipeline
from arxiv_today.bot import run_bot


def task(config_path: str | None = None) -> None:
    """Run one digest for compatibility with existing schedulers."""
    config = AppConfig.load(config_path)
    PaperPipeline(config).run()


def main() -> None:
    parser = argparse.ArgumentParser(description="ArXiv Today")
    parser.add_argument(
        "command",
        nargs="?",
        choices=("digest", "bot"),
        default="digest",
        help="run one digest (default) or the long-running Lark command bot",
    )
    parser.add_argument("--config", dest="config_path")
    args = parser.parse_args()
    config = AppConfig.load(args.config_path)
    if args.command == "bot":
        run_bot(config)
    else:
        PaperPipeline(config).run()


if __name__ == "__main__":
    main()
