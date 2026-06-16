from __future__ import annotations

import os
from pathlib import Path

from loguru import logger
import pyarrow as pa
import pyarrow.parquet as pq

from settings import (
    CONFIG,
    FACT_DIR,
)
from utils import iter_month_rows, parse_float, parse_int

os.environ.setdefault("ARROW_USER_SIMD_LEVEL", "NONE")


def lakehouse_columns(lakehouse_config: dict) -> tuple[dict[str, str], set[str], set[str]]:
    return (
        lakehouse_config["raw_to_curated_columns"],
        set(lakehouse_config["integer_columns"]),
        set(lakehouse_config["float_columns"]),
    )


def lakehouse_schema(lakehouse_config: dict) -> pa.Schema:
    raw_to_curated, integer_columns, float_columns = lakehouse_columns(lakehouse_config)
    string_columns = set(raw_to_curated.values()) - integer_columns - float_columns
    return pa.schema(
        [
            *(pa.field(col, pa.int64()) for col in sorted(integer_columns)),
            *(pa.field(col, pa.float64()) for col in sorted(float_columns)),
            *(pa.field(col, pa.string()) for col in sorted(string_columns)),
        ]
    )


def curate_row(row: dict[str, str], lakehouse_config: dict) -> dict[str, int | float | str | None]:
    raw_to_curated, integer_columns, float_columns = lakehouse_columns(lakehouse_config)
    curated: dict[str, int | float | str | None] = {}
    for raw_col, curated_col in raw_to_curated.items():
        value = row.get(raw_col)
        if curated_col in integer_columns:
            curated[curated_col] = parse_int(value)
        elif curated_col in float_columns:
            curated[curated_col] = parse_float(value)
        else:
            curated[curated_col] = value or None
    return curated


def write_chunk(
    rows: list[dict[str, int | float | str | None]],
    output_path: Path,
    lakehouse_config: dict,
) -> None:
    schema = lakehouse_schema(lakehouse_config)
    arrays = [
        pa.array([row[field.name] for row in rows], type=field.type, from_pandas=False)
        for field in schema
    ]
    table = pa.Table.from_arrays(arrays, schema=schema)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, output_path, compression="zstd")


def build_month(year: int, month: int, lakehouse_config: dict) -> tuple[int, int]:
    partition_dir = FACT_DIR / f"year={year}" / f"month={month:02d}"
    for old_part in partition_dir.glob("part-*.parquet"):
        old_part.unlink()

    rows: list[dict[str, int | float | str | None]] = []
    total_rows = 0
    part_number = 0
    for row in iter_month_rows(year, month):
        rows.append(curate_row(row, lakehouse_config))
        total_rows += 1

        if len(rows) == int(lakehouse_config["chunk_size"]):
            part_number += 1
            write_chunk(rows, partition_dir / f"part-{part_number:04d}.parquet", lakehouse_config)
            rows = []

    if rows:
        part_number += 1
        write_chunk(rows, partition_dir / f"part-{part_number:04d}.parquet", lakehouse_config)

    return total_rows, part_number


def main(dataset_config: dict, lakehouse_config: dict) -> None:
    FACT_DIR.mkdir(parents=True, exist_ok=True)
    total_rows = 0
    total_parts = 0

    for year in dataset_config["years"]:
        for month in dataset_config["months"]:
            rows, parts = build_month(year, month, lakehouse_config)
            total_rows += rows
            total_parts += parts
            logger.info("Wrote {:,} rows for {}-{:02d} across {} parquet files", rows, year, month, parts)

    logger.info("Lakehouse fact table: {}", FACT_DIR)
    logger.info("Total rows: {:,}; parquet files: {}", total_rows, total_parts)


if __name__ == "__main__":
    main(CONFIG["dataset"], CONFIG["lakehouse"])
