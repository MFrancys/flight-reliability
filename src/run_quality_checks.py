from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

import duckdb

from utils import OUTPUT_DIR

os.environ.setdefault("ARROW_USER_SIMD_LEVEL", "NONE")

FACT_DIR = OUTPUT_DIR / "lakehouse" / "curated" / "fact_flight_performance"
QUALITY_DIR = OUTPUT_DIR / "quality"

Status = Literal["pass", "warn", "fail"]
CheckResult = dict[str, str | int]

# Each check: (name, description, sql_predicate, warn_only)
# The predicate selects rows that FAIL the check.
CHECKS: list[tuple[str, str, str, bool]] = [
    (
        "flight_date_not_null",
        "Every fact row should have a flight date.",
        "flight_date is null",
        False,
    ),
    (
        "airline_code_not_null",
        "Every fact row should have an airline code.",
        "airline_code is null or airline_code = ''",
        False,
    ),
    (
        "origin_airport_not_null",
        "Every fact row should have an origin airport.",
        "origin_airport is null or origin_airport = ''",
        False,
    ),
    (
        "dest_airport_not_null",
        "Every fact row should have a destination airport.",
        "dest_airport is null or dest_airport = ''",
        False,
    ),
    (
        "scheduled_departure_time_valid",
        "Scheduled departure time should be HHMM-like (0–2359).",
        "scheduled_dep_time < 0 or scheduled_dep_time > 2359",
        False,
    ),
    (
        "distance_non_negative",
        "Flight distance should be non-negative and within a practical bound.",
        "distance_miles < 0 or distance_miles > 10000",
        False,
    ),
    (
        "arrival_delay_extreme_outlier_watchlist",
        "Extreme arrival delay rows are tracked as a watchlist instead of failing the pipeline.",
        "arrival_delay_minutes < 0 or arrival_delay_minutes > 2000",
        True,  # warn only
    ),
    (
        "binary_cancelled",
        "Cancelled flag should be binary (0 or 1).",
        "cancelled not in (0, 1)",
        False,
    ),
    (
        "binary_diverted",
        "Diverted flag should be binary (0 or 1).",
        "diverted not in (0, 1)",
        False,
    ),
]


def run_checks() -> tuple[int, list[CheckResult]]:
    if not FACT_DIR.exists():
        raise FileNotFoundError(f"Missing lakehouse fact table: {FACT_DIR}")

    parquet_glob = str(FACT_DIR / "year=*/month=*/*.parquet").replace("'", "''")
    con = duckdb.connect()
    con.execute(
        f"""
        create temp view fact_flight_performance as
        select *
        from read_parquet('{parquet_glob}', hive_partitioning=true)
        """
    )

    total_rows: int = con.execute("select count(*) from fact_flight_performance").fetchone()[0]

    results = []
    for name, description, predicate, warn_only in CHECKS:
        rows_failed: int = con.execute(
            f"select count(*) from fact_flight_performance where {predicate}"
        ).fetchone()[0]

        if rows_failed == 0:
            status: Status = "pass"
        elif warn_only:
            status = "warn"
        else:
            status = "fail"

        results.append({
            "name": name,
            "status": status,
            "rows_failed": rows_failed,
            "description": description,
        })

    con.close()
    return total_rows, results


def write_reports(total_rows: int, checks: list[CheckResult]) -> None:
    QUALITY_DIR.mkdir(parents=True, exist_ok=True)

    payload = {
        "total_rows": total_rows,
        "checks": checks,
        "summary": {
            "checks": len(checks),
            "passed": sum(c["status"] == "pass" for c in checks),
            "warnings": sum(c["status"] == "warn" for c in checks),
            "failed": sum(c["status"] == "fail" for c in checks),
        },
    }
    (QUALITY_DIR / "data_quality_report.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )

    lines = [
        "# Data Quality Report",
        "",
        f"Rows evaluated: {total_rows:,}",
        "",
        "| Check | Status | Rows Flagged | Description |",
        "|---|---:|---:|---|",
        *[
            f"| {c['name']} | {str(c['status']).upper()} | {int(c['rows_failed']):,} | {c['description']} |"
            for c in checks
        ],
        "",
    ]
    (QUALITY_DIR / "data_quality_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    total_rows, checks = run_checks()
    write_reports(total_rows, checks)
    failed = sum(c["status"] == "fail" for c in checks)
    warned = sum(c["status"] == "warn" for c in checks)
    print(f"Evaluated {total_rows:,} rows across {len(checks)} checks")
    print(f"Passed: {len(checks) - failed - warned}; warnings: {warned}; failed: {failed}")


if __name__ == "__main__":
    main()
