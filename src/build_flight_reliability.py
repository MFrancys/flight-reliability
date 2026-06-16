from __future__ import annotations

import csv
import os
from collections import defaultdict
from pathlib import Path

from loguru import logger

from settings import (
    CONFIG,
    FIGURE_DIR,
    OUTPUT_DIR,
    PROCESSED_DIR,
)
from utils import iter_month_rows, parse_float, rank_route_opportunity

os.environ.setdefault("MPLCONFIGDIR", str(OUTPUT_DIR / ".matplotlib-cache"))

import matplotlib.pyplot as plt  # noqa: E402


Row = dict[str, str | int | float]
Stats = dict[str, int | float | list[float]]


# ---------------------------------------------------------------------------
# Metric accumulation
# ---------------------------------------------------------------------------

def new_stats() -> Stats:
    return {
        "flights": 0,
        "arrival_delay_sum": 0.0,
        "arrival_delay_count": 0,
        "arrival_delays": [],
        "arrival_late_15": 0,
        "departure_late_15": 0,
        "cancelled": 0,
        "diverted": 0,
        "severe_arrival_delay": 0,
        "distance_sum": 0.0,
        "distance_count": 0,
    }


def add_row(stats: Stats, row: dict[str, str]) -> None:
    stats["flights"] += 1

    arrival_delay = parse_float(row.get("ArrDelayMinutes"))
    if arrival_delay is not None:
        stats["arrival_delay_sum"] += arrival_delay
        stats["arrival_delay_count"] += 1
        stats["arrival_delays"].append(arrival_delay)
        stats["severe_arrival_delay"] += int(arrival_delay >= 60)

    distance = parse_float(row.get("Distance"))
    if distance is not None:
        stats["distance_sum"] += distance
        stats["distance_count"] += 1

    stats["arrival_late_15"] += _binary(row.get("ArrDel15"))
    stats["departure_late_15"] += _binary(row.get("DepDel15"))
    stats["cancelled"] += _binary(row.get("Cancelled"))
    stats["diverted"] += _binary(row.get("Diverted"))


def stats_metrics(stats: Stats, score_weights: dict) -> Row:
    flights = int(stats["flights"])
    arrival_delay_rate = _rate(float(stats["arrival_late_15"]), flights)
    cancellation_rate = _rate(float(stats["cancelled"]), flights)
    diversion_rate = _rate(float(stats["diverted"]), flights)
    severe_rate = _rate(float(stats["severe_arrival_delay"]), flights)
    score = max(
        0,
        min(
            100,
            100
            - score_weights["cancellation"] * cancellation_rate
            - score_weights["diversion"] * diversion_rate
            - score_weights["arrival_delay"] * arrival_delay_rate
            - score_weights["severe_delay"] * severe_rate,
        ),
    )

    return {
        "flights": flights,
        "avg_arrival_delay_min": round(
            _rate(float(stats["arrival_delay_sum"]), float(stats["arrival_delay_count"])),
            2,
        ),
        "p90_arrival_delay_min": round(_percentile(stats["arrival_delays"], 0.90), 2),
        "arrival_delay_rate": round(arrival_delay_rate, 4),
        "departure_delay_rate": round(_rate(float(stats["departure_late_15"]), flights), 4),
        "cancellation_rate": round(cancellation_rate, 4),
        "diversion_rate": round(diversion_rate, 4),
        "severe_arrival_delay_rate": round(severe_rate, 4),
        "avg_distance_miles": round(_rate(float(stats["distance_sum"]), float(stats["distance_count"])), 1),
        "reliability_score": round(score, 2),
    }


# ---------------------------------------------------------------------------
# Small pure helpers
# ---------------------------------------------------------------------------

def _binary(value: str | None) -> int:
    number = parse_float(value)
    return int(number == 1.0)


def _rate(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(round((len(ordered) - 1) * fraction))
    return ordered[index]


def _dep_hour(value: str | None) -> int | None:
    number = parse_float(value)
    if number is None:
        return None
    # Floor-divide HHMM to the hour; % 24 folds the 2400 midnight code to hour 0.
    return (int(number) // 100) % 24


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


# ---------------------------------------------------------------------------
# Derived views used by both save_figures and write_report
# ---------------------------------------------------------------------------

def _hourly_profile(data_marts: dict[str, list[Row]]) -> dict[int, tuple[float, float]]:
    """Returns {hour: (total_flights, weighted_late_count)}."""
    hourly: dict[int, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for row in data_marts["airport_departure_windows"]:
        hour = int(row["dep_hour"])
        flights = int(row["flights"])
        hourly[hour][0] += flights
        hourly[hour][1] += flights * float(row["arrival_delay_rate"])
    return {hour: (vals[0], vals[1]) for hour, vals in hourly.items()}


# ---------------------------------------------------------------------------
# Ingestion and aggregation
# ---------------------------------------------------------------------------

def iter_raw_rows(
    dataset_config: dict,
    delay_reason_columns: list[str],
) -> tuple[int, dict[str, Stats], dict[str, Stats], dict[str, Stats], dict[str, float]]:
    airline_groups: dict[str, Stats] = defaultdict(new_stats)
    route_airline_groups: dict[str, Stats] = defaultdict(new_stats)
    airport_hour_groups: dict[str, Stats] = defaultdict(new_stats)
    delay_reason_minutes = {col: 0.0 for col in delay_reason_columns}
    total_rows = 0

    for year in dataset_config["years"]:
        for month in dataset_config["months"]:
            for row in iter_month_rows(year, month):
                total_rows += 1
                airline = row["Reporting_Airline"]
                origin = row["Origin"]
                dest = row["Dest"]
                route_key = "|".join([
                    airline,
                    f"{origin}-{dest}",
                    f"{row['OriginCityName']} to {row['DestCityName']}",
                    origin,
                    dest,
                ])

                add_row(airline_groups[airline], row)
                add_row(route_airline_groups[route_key], row)
                dep_hour = _dep_hour(row.get("CRSDepTime"))
                if dep_hour is not None:
                    add_row(airport_hour_groups[f"{origin}|{dep_hour:02d}"], row)

                for col in delay_reason_columns:
                    delay_reason_minutes[col] += parse_float(row.get(col)) or 0.0

    return total_rows, airline_groups, route_airline_groups, airport_hour_groups, delay_reason_minutes


def rows_from_groups(
    groups: dict[str, Stats],
    field_names: list[str],
    score_weights: dict,
    minimum_flights: int = 0,
) -> list[Row]:
    rows = []
    for key, stats in groups.items():
        if int(stats["flights"]) < minimum_flights:
            continue
        row = dict(zip(field_names, key.split("|"), strict=True))
        row.update(stats_metrics(stats, score_weights))
        rows.append(row)

    rows.sort(key=lambda r: (float(r["reliability_score"]), -int(r["flights"])))
    return rows


def build_data_marts(
    dataset_config: dict,
    score_weights: dict,
    delay_reason_columns: list[str],
) -> tuple[int, dict[str, list[Row]]]:
    total_rows, airline_groups, route_groups, airport_hour_groups, delay_minutes = iter_raw_rows(
        dataset_config,
        delay_reason_columns,
    )
    total_delay = sum(delay_minutes.values())

    delay_reason_rows = sorted(
        [
            {
                "delay_reason": reason,
                "delay_minutes": round(minutes, 2),
                "share_of_explained_delay": round(_rate(minutes, total_delay), 4),
            }
            for reason, minutes in delay_minutes.items()
        ],
        key=lambda r: float(r["delay_minutes"]),
        reverse=True,
    )

    data_marts = {
        "airline_reliability": rows_from_groups(airline_groups, ["Reporting_Airline"], score_weights),
        "route_airline_reliability": rows_from_groups(
            route_groups,
            ["Reporting_Airline", "route", "route_market", "Origin", "Dest"],
            score_weights,
            minimum_flights=100,
        ),
        "airport_departure_windows": rows_from_groups(airport_hour_groups, ["Origin", "dep_hour"], score_weights),
        "delay_reason_mix": delay_reason_rows,
    }
    return total_rows, data_marts


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_csv(path: Path, rows: list[Row]) -> None:
    if not rows:
        raise ValueError(f"No rows to write for {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def save_data_marts(data_marts: dict[str, list[Row]]) -> None:
    for name, rows in data_marts.items():
        save_csv(PROCESSED_DIR / f"{name}.csv", rows)


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------

def _barh(path: Path, labels: list[str], values: list[float], title: str, xlabel: str, color: str) -> None:
    fig, ax = plt.subplots(figsize=(11, 6))
    positions = range(len(labels))
    ax.barh(positions, values, color=color)
    ax.set_yticks(positions, labels)
    ax.invert_yaxis()
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def save_figures(data_marts: dict[str, list[Row]]) -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)

    airline = sorted(data_marts["airline_reliability"], key=lambda r: float(r["reliability_score"]), reverse=True)
    _barh(
        FIGURE_DIR / "airline_reliability.png",
        [str(r["Reporting_Airline"]) for r in airline],
        [float(r["reliability_score"]) for r in airline],
        "Carrier Reliability Score, Q1 2019",
        "Reliability score",
        "#287271",
    )

    hourly = _hourly_profile(data_marts)
    hours = sorted(hourly)
    rates = [_rate(hourly[h][1], hourly[h][0]) for h in hours]
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(hours, rates, marker="o", color="#2f4858")
    ax.set_title("Departure Hour Risk Profile")
    ax.set_xlabel("Scheduled departure hour")
    ax.set_ylabel("Arrival delay rate")
    ax.set_xticks(range(0, 24, 2))
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / "departure_hour_risk.png", dpi=180)
    plt.close(fig)

    top_routes = rank_route_opportunity(data_marts["route_airline_reliability"])[:15]
    _barh(
        FIGURE_DIR / "route_opportunity.png",
        [f"{r['route']} ({r['Reporting_Airline']})" for r in top_routes],
        [float(r["late_arrivals"]) for r in top_routes],
        "Highest Route-Level Delay Opportunity",
        "Estimated late arrivals",
        "#5f6f52",
    )

    reason = data_marts["delay_reason_mix"]
    _barh(
        FIGURE_DIR / "delay_reason_mix.png",
        [str(r["delay_reason"]).replace("Delay", "") for r in reason],
        [float(r["share_of_explained_delay"]) for r in reason],
        "Explained Delay Minutes by Cause",
        "Share of explained delay minutes",
        "#b85c38",
    )


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def write_report(total_rows: int, data_marts: dict[str, list[Row]]) -> None:
    airline = sorted(data_marts["airline_reliability"], key=lambda r: float(r["reliability_score"]), reverse=True)
    strongest = airline[0]
    weakest = airline[-1]

    route_opportunity = rank_route_opportunity(data_marts["route_airline_reliability"])[:5]

    hourly = _hourly_profile(data_marts)
    high_volume = {h: vals for h, vals in hourly.items() if vals[0] >= 10_000}
    riskiest_hour, (hour_flights, weighted_late) = max(
        high_volume.items(),
        key=lambda item: _rate(item[1][1], item[1][0]),
    )

    top_reason = data_marts["delay_reason_mix"][0]

    lines = [
        "# Flight Reliability Intelligence Report",
        "",
        "## Scope",
        "",
        f"This analysis covers {total_rows:,} scheduled U.S. carrier flights from January through March 2019 using Bureau of Transportation Statistics on-time performance data.",
        "",
        "## Key Findings",
        "",
        f"1. The strongest carrier by composite reliability score is {strongest['Reporting_Airline']} with a score of {strongest['reliability_score']}.",
        f"2. The weakest carrier by composite reliability score is {weakest['Reporting_Airline']} with a score of {weakest['reliability_score']}.",
        f"3. Among high-volume departure windows, the highest-risk scheduled departure hour is {riskiest_hour:02d}:00 with a {_pct(_rate(weighted_late, hour_flights))} arrival delay rate across {int(hour_flights):,} flights.",
        f"4. The largest explained delay category is {top_reason['delay_reason']}, representing {_pct(float(top_reason['share_of_explained_delay']))} of explained delay minutes.",
        "",
        "## Highest Route-Level Opportunities",
        "",
        "| Airline | Route | Market | Flights | Arrival Delay Rate | Estimated Late Arrivals | Reliability Score |",
        "|---|---:|---|---:|---:|---:|---:|",
    ]

    for row in route_opportunity:
        lines.append(
            f"| {row['Reporting_Airline']} | {row['route']} | {row['route_market']} | "
            f"{int(row['flights']):,} | {_pct(float(row['arrival_delay_rate']))} | "
            f"{int(row['late_arrivals']):,} | {float(row['reliability_score']):.2f} |"
        )

    lines.extend(
        [
            "",
            "## Recommendations",
            "",
            "- Prioritize route-level interventions where both volume and delay rate are high. These routes create the biggest customer impact and the clearest operational ROI.",
            "- Investigate late-afternoon and evening departure banks separately from early-day operations because delay propagation usually compounds through the network.",
            "- Treat carrier, NAS, and late-aircraft delay as different operating problems. A single average-delay chart hides the root cause split.",
            "- Add a weekly refresh and alerting layer for routes whose reliability score drops below an agreed service threshold.",
            "",
            "## Engineering Notes",
            "",
            "- The pipeline streams the raw ZIP files directly and writes repeatable CSV data marts.",
            "- Metric definitions are explicit and can be tuned without rewriting the full analysis.",
            "- The current project is batch-oriented. A production version should add tests, orchestration, data quality checks, and dashboard access controls.",
            "",
            "## Limitations",
            "",
            "- This analysis covers Q1 2019 only.",
            "- Delay cause fields are populated mainly for delayed flights, so cause-share charts describe explained delay minutes, not every operational issue.",
            "- Carrier codes are used as reported by BTS; a production-facing version should join a carrier dimension table for full names.",
            "",
        ]
    )

    (OUTPUT_DIR / "flight_reliability_report.md").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(
    dataset_config: dict,
    score_weights: dict,
    delay_reason_columns: list[str],
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)

    total_rows, data_marts = build_data_marts(dataset_config, score_weights, delay_reason_columns)
    save_data_marts(data_marts)
    save_figures(data_marts)
    write_report(total_rows, data_marts)

    logger.info("Loaded {:,} flights", total_rows)
    logger.info("Wrote outputs to {}", OUTPUT_DIR)


if __name__ == "__main__":
    main(CONFIG["dataset"], CONFIG["reliability_score"]["weights"], CONFIG["delay_reason_columns"])
