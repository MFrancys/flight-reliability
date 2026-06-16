from __future__ import annotations

import csv
import zipfile
from collections.abc import Iterator
from pathlib import Path

from settings import DATA_DIR


def monthly_zip_name(year: int, month: int) -> str:
    return f"On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{year}_{month}.zip"


def monthly_zip_path(year: int, month: int) -> Path:
    return DATA_DIR / monthly_zip_name(year, month)


def csv_name_in_archive(archive: zipfile.ZipFile, zip_path: Path) -> str:
    csv_names = [n for n in archive.namelist() if n.endswith(".csv")]
    if len(csv_names) != 1:
        raise ValueError(f"Expected exactly one CSV in {zip_path}, found {csv_names}")
    return csv_names[0]


def iter_month_rows(year: int, month: int) -> Iterator[dict[str, str]]:
    zip_path = monthly_zip_path(year, month)
    if not zip_path.exists():
        raise FileNotFoundError(f"Missing raw data file: {zip_path}")

    with zipfile.ZipFile(zip_path) as archive:
        with archive.open(csv_name_in_archive(archive, zip_path)) as raw_file:
            text_file = (line.decode("utf-8-sig") for line in raw_file)
            yield from csv.DictReader(text_file)


def parse_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def parse_float(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def rank_route_opportunity(routes: list[dict]) -> list[dict]:
    """Add an estimated `late_arrivals` count to each route and rank, biggest impact first."""
    enriched = [
        {**row, "late_arrivals": round(int(row["flights"]) * float(row["arrival_delay_rate"]))}
        for row in routes
    ]
    enriched.sort(key=lambda r: (int(r["late_arrivals"]), float(r["arrival_delay_rate"])), reverse=True)
    return enriched
