from __future__ import annotations

import json
import os
from typing import Literal

import duckdb
from loguru import logger

from settings import CONFIG, FACT_DIR, QUALITY_DIR

os.environ.setdefault("ARROW_USER_SIMD_LEVEL", "NONE")

Status = Literal["pass", "warn", "fail"]
CheckResult = dict[str, str | int]

def run_checks(quality_checks: list[dict]) -> tuple[int, list[CheckResult]]:
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
    for check in quality_checks:
        name = check["name"]
        description = check["description"]
        predicate = check["predicate"]
        warn_only = bool(check["warn_only"])
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


def main(quality_checks: list[dict]) -> None:
    total_rows, checks = run_checks(quality_checks)
    write_reports(total_rows, checks)
    failed = sum(c["status"] == "fail" for c in checks)
    warned = sum(c["status"] == "warn" for c in checks)
    logger.info("Evaluated {:,} rows across {} checks", total_rows, len(checks))
    logger.info("Passed: {}; warnings: {}; failed: {}", len(checks) - failed - warned, warned, failed)


if __name__ == "__main__":
    main(CONFIG["quality_checks"])
