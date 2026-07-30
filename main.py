"""Command-line entry point."""

from arxiv_today import AppConfig, PaperPipeline


def task(config_path: str | None = None) -> None:
    config = AppConfig.load(config_path)
    PaperPipeline(config).run()


if __name__ == "__main__":
    task()
