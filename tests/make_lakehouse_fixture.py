"""Generate a tiny but schema-valid lakehouse partition for CI.

CI has no access to the multi-hundred-MB BTS downloads, so this writes a small
synthetic fact partition that lets `dbt build` exercise every model and data
test end-to-end. Reuses build_lakehouse.SCHEMA / write_chunk so the fixture can
never drift from the real curated schema.

Set FIXTURE_FACT_DIR to write somewhere other than the default fact table.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import build_lakehouse as bl

ROW_COUNT = 160  # > 100 so the route mart's `having count(*) >= 100` keeps a row


def make_row(i: int) -> dict[str, int | float | str | None]:
    return {
        "year": 2019,
        "month": 1,
        "day_of_week": (i % 7) + 1,
        "flight_number": 1000 + i,
        # 0600–2300 → hours 6..23, all inside the accepted_range test.
        "scheduled_dep_time": 600 + (i % 18) * 100,
        "departure_delayed_15": i % 2,
        "arrival_delayed_15": i % 2,
        "cancelled": 0,
        "diverted": 0,
        "departure_delay_minutes": float(i % 30),
        "arrival_delay_minutes": float(i % 30),
        "distance_miles": 733.0,
        "carrier_delay_minutes": float(i % 10),
        "weather_delay_minutes": 0.0,
        "nas_delay_minutes": float(i % 5),
        "security_delay_minutes": 0.0,
        "late_aircraft_delay_minutes": float(i % 8),
        "flight_date": f"2019-01-{(i % 28) + 1:02d}",
        "airline_code": "AA",
        "tail_number": f"N{i:03d}AA",
        "origin_airport": "LGA",
        "origin_city": "New York, NY",
        "dest_airport": "ORD",
        "dest_city": "Chicago, IL",
        "cancellation_code": None,
    }


def main() -> None:
    fact_dir = Path(os.environ.get("FIXTURE_FACT_DIR", bl.FACT_DIR))
    output_path = fact_dir / "year=2019" / "month=01" / "part-0001.parquet"
    bl.write_chunk([make_row(i) for i in range(ROW_COUNT)], output_path)
    print(f"Wrote {ROW_COUNT}-row fixture to {output_path}")


if __name__ == "__main__":
    main()
