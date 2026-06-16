# Flight Reliability Intelligence: Step-by-Step Walkthrough

This document explains the project from first principles: what problem it solves,
where the data comes from, how each pipeline step works, how the dashboard is
built, and how to explain the engineering decisions during code review.

## 1. Project Goal

The project turns raw U.S. Bureau of Transportation Statistics flight records
into a reliability intelligence product for airline operations.

The main business question is:

```text
Which airlines, routes, departure windows, and delay causes create the largest
reliability risk, and where should an operator intervene first?
```

The result is not only a chart. The project shows a complete analytics product:

```text
Raw BTS ZIP files
  -> curated Parquet lakehouse
  -> quality checks
  -> dbt staging and marts
  -> processed CSV marts
  -> executive report
  -> browser dashboard
```

## 2. Data Source

The project uses Bureau of Transportation Statistics Reporting Carrier
On-Time Performance data.

Download base URL:

```text
https://transtats.bts.gov/PREZIP
```

The local portfolio dataset uses Q1 2019:

```text
https://transtats.bts.gov/PREZIP/On_Time_Reporting_Carrier_On_Time_Performance_1987_present_2019_1.zip
https://transtats.bts.gov/PREZIP/On_Time_Reporting_Carrier_On_Time_Performance_1987_present_2019_2.zip
https://transtats.bts.gov/PREZIP/On_Time_Reporting_Carrier_On_Time_Performance_1987_present_2019_3.zip
```

By default, the project expects raw files outside the repository:

```text
../data/
```

That keeps large raw files out of Git.

## 3. Repository Structure

The important folders are:

```text
src/
  settings.py                  Environment paths and config loader
  utils.py                     Shared parsing, raw row iteration, ranking helpers
  download_bts_data.py         Downloads monthly BTS ZIP files
  build_lakehouse.py           Builds curated partitioned Parquet files
  run_quality_checks.py        Runs DuckDB quality checks over the lakehouse
  build_flight_reliability.py  Builds CSV marts, figures, and Markdown report
  build_dashboard.py           Injects data into the dashboard template

models/
  sources.yml                  dbt source definition over curated Parquet
  staging/stg_flights.sql      Typed and standardized flight records
  marts/*.sql                  Airline, route, hour, and delay reason marts

macros/
  reliability_score.sql        dbt reliability score formula
  flight_reliability_metrics.sql
                               Shared dbt aggregate metric block
  accepted_range.sql           Custom dbt data test

dashboard/
  template.html                Dashboard source template
  index.html                   Generated self-contained dashboard

docs/
  architecture.md              System architecture and production path
  dbt_guide.md                 dbt-specific setup and explanation
  step_by_step_walkthrough.md  This document

tests/
  test_metrics.py              Python unit tests for metric helpers
  assert_reliability_score_bounds.sql
                               dbt assertion test
```

## 4. Configuration

Environment-specific paths live in:

```text
src/settings.py
```

Examples:

```python
PROJECT_ROOT
DATA_DIR
OUTPUT_DIR
DASHBOARD_DIR
CONFIG_PATH
```

These can be overridden with environment variables when needed.

Business and data-product configuration lives in:

```text
config.yaml
```

Examples:

```yaml
dataset:
  years: [2020, 2021, 2022, 2023, 2024, 2025, 2026]
  months: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
```

The reliability score weights also live there:

```yaml
reliability_score:
  weights:
    cancellation: 45
    diversion: 30
    arrival_delay: 20
    severe_delay: 5
```

These weights match the dbt macro in:

```text
macros/reliability_score.sql
```

That symmetry matters because the Python pipeline and dbt layer should tell the
same business story.

## 5. Step-by-Step Pipeline

### Step 1: Download Raw BTS ZIP Files

Script:

```text
src/download_bts_data.py
```

What it does:

- Builds the BTS monthly ZIP filename from year and month.
- Downloads the file from `https://transtats.bts.gov/PREZIP`.
- Writes files to `../data`.
- Reuses cached files when they already exist.

Run:

```bash
python3 src/download_bts_data.py
```

### Step 2: Build the Curated Lakehouse

Script:

```text
src/build_lakehouse.py
```

What it does:

- Streams rows directly from each raw ZIP file.
- Selects the columns needed for reliability analysis.
- Casts numeric columns into integers or floats.
- Writes compressed Parquet files.
- Partitions data by year and month.

Output:

```text
outputs/lakehouse/curated/fact_flight_performance/
  year=2019/month=01/*.parquet
  year=2019/month=02/*.parquet
  year=2019/month=03/*.parquet
```

Run:

```bash
python3 src/build_lakehouse.py
```

Why this design is strong:

- Parquet is columnar, compressed, and efficient for analytics.
- Year/month partitioning matches the source file cadence.
- The same design can scale from a local sample to decades of history.

### Step 3: Run Data Quality Checks

Script:

```text
src/run_quality_checks.py
```

What it does:

- Creates a DuckDB view over the Parquet fact table.
- Runs each quality rule as a SQL predicate.
- Counts failing rows.
- Writes JSON and Markdown quality reports.

Output:

```text
outputs/quality/data_quality_report.json
outputs/quality/data_quality_report.md
```

Run:

```bash
python3 src/run_quality_checks.py
```

Current local result:

```text
Evaluated 1,749,234 rows across 9 checks
Passed: 8; warnings: 1; failed: 0
```

Why this design is strong:

- Quality checks run in DuckDB instead of row-by-row Python.
- Rules are short, readable SQL predicates.
- The checks scale better over large columnar data.

### Step 4: Build Reliability Marts and Report

Script:

```text
src/build_flight_reliability.py
```

What it does:

- Reads raw BTS rows.
- Aggregates metrics by airline.
- Aggregates metrics by airline and route.
- Aggregates departure-hour risk.
- Aggregates delay reason mix.
- Writes processed CSV marts.
- Writes static figures.
- Writes an executive Markdown report.

Outputs:

```text
outputs/processed/airline_reliability.csv
outputs/processed/route_airline_reliability.csv
outputs/processed/airport_departure_windows.csv
outputs/processed/delay_reason_mix.csv
outputs/flight_reliability_report.md
```

Run:

```bash
python3 src/build_flight_reliability.py
```

Important implementation detail:

- The code uses small functions instead of classes.
- Metric accumulation uses plain dictionaries and helper functions.
- Shared ranking logic lives in `src/utils.py`.

### Step 5: Build the Dashboard

Script:

```text
src/build_dashboard.py
```

Template:

```text
dashboard/template.html
```

Output:

```text
dashboard/index.html
```

What it does:

- Reads the processed CSV marts.
- Converts metric columns from strings into numbers.
- Ranks routes by estimated late arrivals.
- Builds a compact JSON payload.
- Injects that payload into the dashboard HTML template.

Run:

```bash
python3 src/build_dashboard.py
```

Serve locally:

```bash
python3 -m http.server 8765
```

Open:

```text
http://localhost:8765/dashboard/index.html
```

Current verified dashboard signals:

```text
Title: Flight Reliability Intelligence
Charts: 3
Route rows displayed: 30
Scheduled flights: 1,749,234
Reliability score: 94.7
```

## 6. dbt Layer

The dbt layer is the analytics engineering version of the pipeline.

Key files:

```text
models/sources.yml
models/staging/stg_flights.sql
models/marts/mart_airline_reliability.sql
models/marts/mart_route_reliability.sql
models/marts/mart_departure_hour_reliability.sql
models/marts/mart_delay_reason_mix.sql
macros/reliability_score.sql
macros/flight_reliability_metrics.sql
```

What dbt adds:

- Source definitions
- Staging model
- Mart models
- Reusable macros
- Data tests
- Dashboard exposure metadata
- Documentation and lineage

Useful commands:

```bash
dbt parse --profiles-dir profiles --no-partial-parse
dbt compile --profiles-dir profiles
dbt build --profiles-dir profiles
```

Current validation:

```text
dbt parse: passed with no deprecation warnings
dbt compile: passed
```

## 7. Reliability Metrics

The project does not rely on average delay alone. It uses several operational
signals:

```text
arrival_delay_rate
departure_delay_rate
cancellation_rate
diversion_rate
severe_arrival_delay_rate
reliability_score
```

The reliability score is intentionally simple and auditable:

```text
100
- 45 * cancellation_rate
- 30 * diversion_rate
- 20 * arrival_delay_rate
- 5  * severe_arrival_delay_rate
```

This score is a product metric, not an aviation law. In a real business setting,
the weights should be reviewed with operations, customer experience, and finance
stakeholders.

## 8. Dashboard Views

The dashboard has four main sections:

### Carrier Reliability

Shows the composite reliability score by airline.

Why a lollipop chart:

- Carrier scores are tightly clustered.
- Bars from zero would hide the meaningful spread.
- A zoomed lollipop chart shows the real differences clearly.

### Delay Cause Mix

Shows the share of explained delay minutes by cause.

Current top causes:

```text
Late aircraft delay
Carrier delay
NAS delay
Weather delay
Security delay
```

### Departure Hour Risk

Shows arrival delay rate by scheduled departure hour.

This helps identify delay propagation patterns across the day.

### Route Opportunity Queue

Prioritizes routes by estimated late arrivals.

This is useful because a route with moderate delay rate and very high volume may
be more important than a tiny route with an extreme delay rate.

## 9. Testing and Validation

Python tests:

```bash
pytest
```

Current result:

```text
12 passed
```

Syntax check:

```bash
python -m compileall src tests main.py
```

dbt checks:

```bash
dbt parse --profiles-dir profiles --no-partial-parse
dbt compile --profiles-dir profiles
```

Quality checks:

```bash
python3 src/run_quality_checks.py
```

Together, these checks prove:

- Python metric helpers behave as expected.
- dbt models and macros compile.
- source and mart schema tests are valid.
- generated lakehouse data passes operational quality rules.

## 10. How to Explain the Project in a Review

Use this short story:

```text
I built a local-first airline reliability intelligence product from raw BTS
monthly ZIP files. The pipeline streams raw source data into partitioned Parquet,
runs DuckDB quality checks, models reliability metrics in Python and dbt, and
ships an interactive static dashboard for operations analysis.
```

Then explain the engineering judgment:

- Raw data is kept outside Git.
- Generated outputs are ignored by `.gitignore`.
- Shared helpers remove repeated ZIP parsing and route ranking logic.
- dbt macros remove repeated reliability metric SQL.
- Quality checks run in SQL for speed and readability.
- The dashboard is static and dependency-light, which makes it easy to review.
- The production path is clear: object storage, dbt, orchestration, observability,
  and a governed semantic layer.

## 11. Common Commands

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the full pipeline:

```bash
python3 main.py
```

Run dashboard only:

```bash
python3 src/build_dashboard.py
python3 -m http.server 8765
```

Open dashboard:

```text
http://localhost:8765/dashboard/index.html
```

Run tests:

```bash
pytest
```

Run dbt compile:

```bash
dbt compile --profiles-dir profiles
```

Check Git state:

```bash
git status --short
```

## 12. Current Local Notes

The first commit was created with:

```text
Initial commit: add flight reliability intelligence pipeline
```

The local dashboard server can be started with:

```bash
python3 -m http.server 8765
```

The dashboard URL is:

```text
http://localhost:8765/dashboard/index.html
```

Unrelated local folders should stay out of commits unless intentionally needed:

```text
.claude/
Cohort Credit Risk/
```

## 13. Review Checklist

Before presenting or committing new changes, run:

```bash
pytest
python -m compileall src tests main.py
dbt parse --profiles-dir profiles --no-partial-parse
dbt compile --profiles-dir profiles
python3 src/run_quality_checks.py
python3 src/build_dashboard.py
```

A clean review-ready state should have:

- no Python test failures
- no dbt parse warnings
- no dbt compile errors
- no generated cache files staged
- no raw data ZIPs staged
- no local-only files staged
- clear, small diffs
