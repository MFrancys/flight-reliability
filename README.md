# Flight Reliability Intelligence

Portfolio project by Francys Lanza

[![CI](https://github.com/MFrancysBegini/flight-reliability-intelligence/actions/workflows/ci.yml/badge.svg)](https://github.com/MFrancysBegini/flight-reliability-intelligence/actions/workflows/ci.yml)

> **CI:** every push runs the Python unit tests (`pytest`) and a full `dbt build`
> (models + data tests) against a synthetic lakehouse fixture. See
> [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

## Executive Summary

This project turns raw U.S. Bureau of Transportation Statistics on-time flight records into a reliability intelligence layer for airline operations. The full source domain spans 1987-2026, more than 100 million records, and roughly 12 GiB of raw storage. The local portfolio build starts with Q1 2019, then structures the project so it can scale into a historical analytics product.

The core question is:

> Which routes, departure windows, and delay causes create the largest reliability risk, and where should an operator intervene first?

The work is designed to show more than exploratory charts. It demonstrates data product thinking: reproducible ingestion, metric design, aggregation strategy, dashboard delivery, visual storytelling, and operational recommendations.

## Why This Stands Out

Principal-level reviewers usually look for judgment: clear problem framing, tradeoffs, reliable code, and the ability to connect analysis to action. This project is structured around those signals.

- Uses real operational data, not a toy dataset.
- Reads raw monthly ZIP files directly, preserving the original source format.
- Defines explicit reliability metrics instead of relying only on average delay.
- Produces reusable route, airline, airport, time-window, and delay-cause data marts.
- Ships a user-facing dashboard from the modeled data layer.
- Separates pipeline code, generated outputs, and narrative reporting.
- Calls out limitations and next steps so the analysis feels production-aware.

## Product Direction

Yes: the final result should be a dashboard, but the dashboard should be presented as the visible layer of a real analytics platform. For a Principal Data Engineer or Analytics Engineer portfolio, the strongest version is:

```text
Raw BTS ZIP files
  -> partitioned analytical storage
  -> tested transformation models
  -> governed metrics
  -> dashboard-ready aggregate tables
  -> operations dashboard
```

This shows you can design for scale, quality, usability, and business action.

## Project Structure

```text
portfolio_flight_reliability/
  README.md
  requirements.txt
  dashboard/
    index.html
  docs/
    architecture.md
    dbt_guide.md
  metrics/
    semantic_layer.yml
  macros/
    accepted_range.sql
    reliability_score.sql
  models/
    sources.yml
    staging/
      stg_flights.sql
      schema.yml
    marts/
      mart_airline_reliability.sql
      mart_route_reliability.sql
      mart_departure_hour_reliability.sql
      mart_delay_reason_mix.sql
      schema.yml
  tests/
    assert_reliability_score_bounds.sql
    test_metrics.py
  analyses/
    high_risk_routes.sql
  dbt_project.yml
  profiles/
    profiles.yml.example
  config.yaml
  main.py
  src/
    settings.py
    utils.py
    download_bts_data.py
    build_lakehouse.py
    build_flight_reliability.py
    build_dashboard.py
    run_quality_checks.py
  outputs/
    lakehouse/
      curated/
        fact_flight_performance/
          year=2019/month=01/*.parquet
          year=2019/month=02/*.parquet
          year=2019/month=03/*.parquet
    processed/
      airline_reliability.csv
      airport_departure_windows.csv
      delay_reason_mix.csv
      route_airline_reliability.csv
    figures/
      airline_reliability.png
      delay_reason_mix.png
      departure_hour_risk.png
      route_opportunity.png
    quality/
      data_quality_report.md
      data_quality_report.json
    flight_reliability_report.md
```

## Data

Source: Bureau of Transportation Statistics Reporting Carrier On-Time Performance data.

Local raw files used by this project:

- `../data/On_Time_Reporting_Carrier_On_Time_Performance_1987_present_2019_1.zip`
- `../data/On_Time_Reporting_Carrier_On_Time_Performance_1987_present_2019_2.zip`
- `../data/On_Time_Reporting_Carrier_On_Time_Performance_1987_present_2019_3.zip`

The current analysis uses January through March 2019.

## Metrics

The project uses several reliability indicators:

- `arrival_delay_rate`: share of flights arriving at least 15 minutes late.
- `departure_delay_rate`: share of flights departing at least 15 minutes late.
- `cancellation_rate`: share of scheduled flights cancelled.
- `diversion_rate`: share of scheduled flights diverted.
- `severe_arrival_delay_rate`: share of flights arriving at least 60 minutes late.
- `reliability_score`: a 0-100 composite score where cancellations, diversions, late arrivals, and severe late arrivals are penalized.

The score is intentionally simple and auditable:

```text
100
- 45 * cancellation_rate
- 30 * diversion_rate
- 20 * arrival_delay_rate
- 5  * severe_arrival_delay_rate
```

This is not a universal aviation truth. It is a product metric that can be tuned with business stakeholders.

## Design Decisions & Tradeoffs

The interesting part of this project is the judgment behind it, not the line count. The decisions worth defending:

- **Two implementations of the same metrics, on purpose.** A streaming Python pipeline (`src/`) and a dbt SQL layer (`models/`) both compute the reliability marts. They are not redundant: the Python path is a zero-infrastructure local fallback, the dbt path is the production direction, and running both lets them **cross-validate** — carrier reliability scores match to the cent across all 17 carriers. The shared score weights live in `config.yaml`, while the dbt score formula lives in `macros/reliability_score.sql`, so drift is visible and reviewable.

- **Quality checks as declarative DuckDB SQL, not row-by-row validation.** An earlier version validated each row in Python with Pydantic. Rewriting the checks as `count(*) WHERE <predicate>` queries dropped the runtime from minutes to **0.6s on 1.75M rows**, made each rule a one-line, reviewable predicate, and pushed the work to the engine that already holds the data. Pydantic is the right tool for request validation; it is the wrong tool for scanning a columnar fact table.

- **Lollipop chart over a bar chart for carrier reliability.** Every carrier scores 90–96. Bars-from-zero render as 18 near-identical rectangles that tell no story; a non-zero bar axis is misleading. A lollipop on a zoomed scale shows the real spread honestly and highlights best/worst — the correct call for tightly-clustered values.

- **Metric definitions centralized because they silently drift.** The departure-hour bug proves the point: `cast(time / 100 as integer)` *rounds* (2359 → 24), while Python's `// 100` *truncates* (2359 → 23). The two layers disagreed for months of analysis until a dbt `accepted_range` test caught it. The fix — `(HHMM // 100) % 24` in both layers — only stays correct because the logic is defined once per layer and tested.

- **Hand-rolled canvas charts, no charting library.** The dashboard ships as a single self-contained HTML file with zero runtime dependencies, which is ideal for a portfolio artifact anyone can open. The tradeoff is more chart code to maintain; for a production app with evolving requirements, a library like Vega-Lite or Recharts would be the better call.

- **Synthetic fixture for CI instead of real data.** CI cannot download hundreds of MB of BTS files per push, so `tests/make_lakehouse_fixture.py` generates a tiny schema-valid partition that reuses the real `build_lakehouse` schema. This keeps `dbt build` running the *actual* models and tests in CI, rather than degrading to a parse-only check.

- **Partition curated data by year and month.** The source arrives as monthly extracts and almost all historical analysis filters by time, so this partitioning matches both the ingestion cadence and the query pattern, and lets the design scale from the Q1 2019 sample to the full 1987–2026 archive without restructuring.

## How To Run

Install dependencies, then run the full pipeline from the project root:

```bash
pip install -r requirements.txt
python3 main.py
```

The dataset scope (years and months) is controlled in one place: `config.yaml`.

To run individual steps while debugging:

```bash
python3 src/build_lakehouse.py
python3 src/run_quality_checks.py
python3 src/build_flight_reliability.py
python3 src/build_dashboard.py
```

Run the unit tests for the metric helpers and reliability score:

```bash
python3 -m pytest tests/test_metrics.py
```

Generated files are written to `outputs/`.

Open the dashboard at:

```text
portfolio_flight_reliability/dashboard/index.html
```

Review the data quality report at:

```text
portfolio_flight_reliability/outputs/quality/data_quality_report.md
```

The dbt layer is scaffolded for `dbt-duckdb` or a cloud warehouse. See:

```text
portfolio_flight_reliability/docs/dbt_guide.md
```

## Portfolio Story

Suggested title for your portfolio:

**Flight Reliability Intelligence: Turning Airline Operations Data Into a Reliability Command Center**

Suggested description:

Built a reproducible analytics pipeline and dashboard over raw BTS on-time performance files to identify reliability risk by carrier, route, airport, departure hour, and delay cause. Designed auditable metrics, generated decision-ready data marts, and translated findings into prioritized operational recommendations.

## Next-Level Extensions

For a stronger principal-level version:

- Add DuckDB for SQL-first transformations over the raw ZIP extracts.
- Add dbt models and tests for metric definitions.
- Replace the static dashboard with Streamlit, Evidence, Apache Superset, Metabase, or a React dashboard backed by DuckDB/Postgres.
- Add prediction: probability of arrival delay given route, carrier, time of day, and airport.
- Add data quality checks for null rates, duplicate keys, and impossible elapsed times.
- Compare Q1 2019 with Q1 2020 or Q1 2023 to show temporal drift.

## Principal-Level Architecture Target

For the full 1987-2026 dataset, the portfolio architecture should emphasize:

- Storage: partition raw and curated data by year and month.
- Query engine: use DuckDB locally or BigQuery/Snowflake/Databricks in the cloud.
- Transformations: model facts and dimensions with dbt.
- Quality: test not-null keys, accepted values, duplicate flight identity, delay bounds, and monthly freshness.
- Metrics: centralize reliability score, delay rates, cancellation rate, and severe-delay rate.
- Dashboard: serve aggregate tables rather than querying 100M+ rows interactively.
- Operations: refresh incrementally when a new monthly BTS file arrives.

## Current Execution Upgrade

The project now includes a runnable platform-style implementation:

- Lakehouse: `build_lakehouse.py` converts raw BTS ZIP CSVs into compressed Parquet partitions.
- Quality: `run_quality_checks.py` runs declarative DuckDB SQL checks over the curated Parquet fact table to evaluate hard checks and anomaly watchlists.
- dbt: `dbt_project.yml`, `models/`, `macros/`, `tests/`, and `analyses/` define the analytics engineering layer.
- Metrics: `metrics/semantic_layer.yml` documents governed reliability metrics.
- Dashboard: `dashboard/index.html` is generated from dashboard-ready marts.

Local run result:

- 1,749,234 rows converted into 19 Parquet files.
- Curated Parquet layer is about 12 MiB for the Q1 2019 local sample.
- Data quality checks: 8 pass, 1 warning, 0 failures.
