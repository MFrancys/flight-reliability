# dbt Layer

## Why dbt Belongs In This Project

dbt turns this from a data visualization project into an analytics engineering project. It demonstrates the habits top companies expect:

- version-controlled SQL transformations
- source definitions
- staging and mart layers
- reusable macros for business logic
- tests for quality and metric bounds
- exposures that connect data models to dashboard products
- documentation and lineage

## Recommended Local Stack

Use `dbt-duckdb` for a local portfolio version because the project already writes partitioned Parquet.

```bash
python3 -m pip install dbt-core dbt-duckdb
```

Then copy the example profile into your dbt profiles directory:

```bash
mkdir -p ~/.dbt
cp portfolio_flight_reliability/profiles/profiles.yml.example ~/.dbt/profiles.yml
```

Run from the project directory:

```bash
cd portfolio_flight_reliability
dbt deps
dbt debug
dbt build
dbt docs generate
dbt docs serve
```

## Production Mapping

The same dbt structure maps cleanly to enterprise platforms:

- BigQuery: external or managed tables over GCS Parquet.
- Snowflake: external tables or loaded tables from cloud storage.
- Databricks: Delta/Iceberg tables over object storage.
- DuckDB: local analytical engine for reproducible portfolio demos.

## Interview Talking Point

The dashboard is not the source of truth. dbt is the governed transformation layer that defines the source-to-mart contract, tests the assumptions, and documents lineage from raw BTS data to executive-facing reliability metrics.
