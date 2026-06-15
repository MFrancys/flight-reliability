from __future__ import annotations

import os
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from config import MONTHS, YEARS
from utils import OUTPUT_DIR, iter_month_rows, parse_float, parse_int

os.environ.setdefault("ARROW_USER_SIMD_LEVEL", "NONE")

LAKEHOUSE_DIR = OUTPUT_DIR / "lakehouse"
FACT_DIR = LAKEHOUSE_DIR / "curated" / "fact_flight_performance"
CHUNK_SIZE = 100_000

RAW_TO_CURATED_COLUMNS = {
    "Year": "year",
    "Month": "month",
    "FlightDate": "flight_date",
    "DayOfWeek": "day_of_week",
    "Reporting_Airline": "airline_code",
    "Flight_Number_Reporting_Airline": "flight_number",
    "Tail_Number": "tail_number",
    "Origin": "origin_airport",
    "OriginCityName": "origin_city",
    "Dest": "dest_airport",
    "DestCityName": "dest_city",
    "CRSDepTime": "scheduled_dep_time",
    "DepDelayMinutes": "departure_delay_minutes",
    "DepDel15": "departure_delayed_15",
    "ArrDelayMinutes": "arrival_delay_minutes",
    "ArrDel15": "arrival_delayed_15",
    "Cancelled": "cancelled",
    "CancellationCode": "cancellation_code",
    "Diverted": "diverted",
    "Distance": "distance_miles",
    "CarrierDelay": "carrier_delay_minutes",
    "WeatherDelay": "weather_delay_minutes",
    "NASDelay": "nas_delay_minutes",
    "SecurityDelay": "security_delay_minutes",
    "LateAircraftDelay": "late_aircraft_delay_minutes",
}

INTEGER_COLUMNS = {
    "year",
    "month",
    "day_of_week",
    "flight_number",
    "scheduled_dep_time",
    "departure_delayed_15",
    "arrival_delayed_15",
    "cancelled",
    "diverted",
}

FLOAT_COLUMNS = {
    "departure_delay_minutes",
    "arrival_delay_minutes",
    "distance_miles",
    "carrier_delay_minutes",
    "weather_delay_minutes",
    "nas_delay_minutes",
    "security_delay_minutes",
    "late_aircraft_delay_minutes",
}

STRING_COLUMNS = set(RAW_TO_CURATED_COLUMNS.values()) - INTEGER_COLUMNS - FLOAT_COLUMNS

SCHEMA = pa.schema(
    [
        *(pa.field(col, pa.int64()) for col in sorted(INTEGER_COLUMNS)),
        *(pa.field(col, pa.float64()) for col in sorted(FLOAT_COLUMNS)),
        *(pa.field(col, pa.string()) for col in sorted(STRING_COLUMNS)),
    ]
)


def curate_row(row: dict[str, str]) -> dict[str, int | float | str | None]:
    curated: dict[str, int | float | str | None] = {}
    for raw_col, curated_col in RAW_TO_CURATED_COLUMNS.items():
        value = row.get(raw_col)
        if curated_col in INTEGER_COLUMNS:
            curated[curated_col] = parse_int(value)
        elif curated_col in FLOAT_COLUMNS:
            curated[curated_col] = parse_float(value)
        else:
            curated[curated_col] = value or None
    return curated


def write_chunk(rows: list[dict[str, int | float | str | None]], output_path: Path) -> None:
    arrays = [
        pa.array([row[field.name] for row in rows], type=field.type, from_pandas=False)
        for field in SCHEMA
    ]
    table = pa.Table.from_arrays(arrays, schema=SCHEMA)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, output_path, compression="zstd")


def build_month(year: int, month: int) -> tuple[int, int]:
    partition_dir = FACT_DIR / f"year={year}" / f"month={month:02d}"
    for old_part in partition_dir.glob("part-*.parquet"):
        old_part.unlink()

    rows: list[dict[str, int | float | str | None]] = []
    total_rows = 0
    part_number = 0
    for row in iter_month_rows(year, month):
        rows.append(curate_row(row))
        total_rows += 1

        if len(rows) == CHUNK_SIZE:
            part_number += 1
            write_chunk(rows, partition_dir / f"part-{part_number:04d}.parquet")
            rows = []

    if rows:
        part_number += 1
        write_chunk(rows, partition_dir / f"part-{part_number:04d}.parquet")

    return total_rows, part_number


def main() -> None:
    FACT_DIR.mkdir(parents=True, exist_ok=True)
    total_rows = 0
    total_parts = 0

    for year in YEARS:
        for month in MONTHS:
            rows, parts = build_month(year, month)
            total_rows += rows
            total_parts += parts
            print(f"Wrote {rows:,} rows for {year}-{month:02d} across {parts} parquet files")

    print(f"Lakehouse fact table: {FACT_DIR}")
    print(f"Total rows: {total_rows:,}; parquet files: {total_parts}")


if __name__ == "__main__":
    main()
