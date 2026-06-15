"""Pipeline entry point.

Usage:
    cd <project_root>
    python main.py

The YEARS / MONTHS scope in src/config.py controls which BTS files are
downloaded and processed. The portfolio default is Q1 2019.
"""
from __future__ import annotations

import sys
import time
from collections.abc import Callable
from pathlib import Path

# Make src/ importable without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from src import build_dashboard, build_flight_reliability, build_lakehouse, download_bts_data, run_quality_checks
from src.config import MONTHS, YEARS

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT.parent / "data"

PipelineStep = tuple[str, Callable[[], None]]


def run_step(name: str, step: Callable[[], None]) -> None:
    print(f"\n=== {name} ===")
    started_at = time.perf_counter()
    step()
    elapsed = time.perf_counter() - started_at
    print(f"Finished {name} in {elapsed:,.1f}s")


def main() -> None:
    steps: list[PipelineStep] = [
        ("Download BTS data", lambda: download_bts_data.main(DATA_DIR, YEARS, MONTHS)),
        ("Build lakehouse", build_lakehouse.main),
        ("Run quality checks", run_quality_checks.main),
        ("Build reliability marts and report", build_flight_reliability.main),
        ("Build dashboard", build_dashboard.main),
    ]

    started_at = time.perf_counter()
    for name, step in steps:
        run_step(name, step)

    elapsed = time.perf_counter() - started_at
    print(f"\nPipeline completed in {elapsed:,.1f}s")


if __name__ == "__main__":
    main()
