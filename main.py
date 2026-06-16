"""Pipeline entry point.

Usage:
    cd <project_root>
    python main.py

The years/months scope in config.yaml controls which BTS files are
downloaded and processed. The portfolio default is Q1 2019.
"""
from __future__ import annotations

import sys
import time
from collections.abc import Callable
from pathlib import Path

from loguru import logger

# Make src/ importable without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from src import build_dashboard, build_flight_reliability, build_lakehouse, download_bts_data, run_quality_checks
from settings import CONFIG, DATA_DIR

PipelineStep = tuple[str, Callable[[], None]]


def run_step(name: str, step: Callable[[], None]) -> None:
    logger.info("=== {} ===", name)
    started_at = time.perf_counter()
    step()
    elapsed = time.perf_counter() - started_at
    logger.info("Finished {} in {:,.1f}s", name, elapsed)


def main() -> None:
    steps: list[PipelineStep] = [
        (
            "Download BTS data",
            lambda: download_bts_data.main(DATA_DIR, CONFIG["dataset"], CONFIG["bts"]),
        ),
        ("Build lakehouse", lambda: build_lakehouse.main(CONFIG["dataset"], CONFIG["lakehouse"])),
        ("Run quality checks", lambda: run_quality_checks.main(CONFIG["quality_checks"])),
        (
            "Build reliability marts and report",
            lambda: build_flight_reliability.main(
                CONFIG["dataset"],
                CONFIG["reliability_score"]["weights"],
                CONFIG["delay_reason_columns"],
            ),
        ),
        ("Build dashboard", lambda: build_dashboard.main(CONFIG["dashboard"])),
    ]

    started_at = time.perf_counter()
    for name, step in steps:
        run_step(name, step)

    elapsed = time.perf_counter() - started_at
    logger.info("Pipeline completed in {:,.1f}s", elapsed)


if __name__ == "__main__":
    main()
