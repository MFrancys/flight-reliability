from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", Path(__file__).resolve().parents[1])).resolve()
DATA_DIR = Path(os.environ.get("DATA_DIR", PROJECT_ROOT.parent / "data")).resolve()
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", PROJECT_ROOT / "outputs")).resolve()
DASHBOARD_DIR = Path(os.environ.get("DASHBOARD_DIR", PROJECT_ROOT / "dashboard")).resolve()
CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", PROJECT_ROOT / "config.yaml")).resolve()

PROCESSED_DIR = OUTPUT_DIR / "processed"
FIGURE_DIR = OUTPUT_DIR / "figures"
LAKEHOUSE_DIR = OUTPUT_DIR / "lakehouse"
FACT_DIR = LAKEHOUSE_DIR / "curated" / "fact_flight_performance"
QUALITY_DIR = OUTPUT_DIR / "quality"
DASHBOARD_TEMPLATE_PATH = DASHBOARD_DIR / "template.html"
DASHBOARD_OUTPUT_PATH = DASHBOARD_DIR / "index.html"


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        return yaml.safe_load(source) or {}


CONFIG = load_config()
