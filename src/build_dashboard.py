from __future__ import annotations

import csv
import json
from pathlib import Path

from utils import OUTPUT_DIR, rank_route_opportunity

PROCESSED_DIR = OUTPUT_DIR / "processed"
DASHBOARD_DIR = Path(__file__).resolve().parents[1] / "dashboard"
TEMPLATE_PATH = DASHBOARD_DIR / "template.html"
PAYLOAD_TOKEN = "__PAYLOAD_JSON__"

METRIC_COLUMNS = [
    "flights",
    "avg_arrival_delay_min",
    "p90_arrival_delay_min",
    "arrival_delay_rate",
    "departure_delay_rate",
    "cancellation_rate",
    "diversion_rate",
    "severe_arrival_delay_rate",
    "avg_distance_miles",
    "reliability_score",
]


def read_csv(name: str) -> list[dict[str, str]]:
    with (PROCESSED_DIR / name).open(encoding="utf-8") as source:
        return list(csv.DictReader(source))


def cast_metrics(row: dict[str, str], keys: list[str]) -> dict[str, str | int | float]:
    result: dict[str, str | int | float] = dict(row)
    for key in keys:
        value = row.get(key, "")
        if not value:
            result[key] = 0
        elif "." in value:
            result[key] = float(value)
        else:
            result[key] = int(value)
    return result


def _departure_hour_series(airport_windows: list[dict]) -> list[dict]:
    hourly: dict[str, dict[str, float]] = {}
    for row in airport_windows:
        hour = str(row["dep_hour"])
        bucket = hourly.setdefault(hour, {"flights": 0.0, "late_weight": 0.0})
        bucket["flights"] += int(row["flights"])
        bucket["late_weight"] += int(row["flights"]) * float(row["arrival_delay_rate"])

    return [
        {
            "dep_hour": int(hour),
            "flights": int(values["flights"]),
            "arrival_delay_rate": values["late_weight"] / values["flights"],
        }
        for hour, values in sorted(hourly.items(), key=lambda item: int(item[0]))
    ]


def build_payload() -> dict[str, object]:
    airline = [cast_metrics(r, METRIC_COLUMNS) for r in read_csv("airline_reliability.csv")]
    routes = [cast_metrics(r, METRIC_COLUMNS) for r in read_csv("route_airline_reliability.csv")]
    airport_windows = [cast_metrics(r, METRIC_COLUMNS) for r in read_csv("airport_departure_windows.csv")]
    delay_reason = [
        cast_metrics(r, ["delay_minutes", "share_of_explained_delay"])
        for r in read_csv("delay_reason_mix.csv")
    ]

    route_opportunity = rank_route_opportunity(routes)
    departure_hours = _departure_hour_series(airport_windows)

    return {
        "airlines": airline,
        "routes": route_opportunity[:500],
        "delayReasons": delay_reason,
        "departureHours": departure_hours,
        "meta": {
            "flights": sum(int(r["flights"]) for r in airline),
            "airlines": len(airline),
            "routes": len(routes),
            "routeRowsDisplayed": min(500, len(route_opportunity)),
        },
    }


def dashboard_html(payload: dict[str, object]) -> str:
    payload_json = json.dumps(payload, separators=(",", ":"))
    return TEMPLATE_PATH.read_text(encoding="utf-8").replace(PAYLOAD_TOKEN, payload_json)


def main() -> None:
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    (DASHBOARD_DIR / "index.html").write_text(dashboard_html(payload), encoding="utf-8")
    print(f"Wrote dashboard to {DASHBOARD_DIR / 'index.html'}")


if __name__ == "__main__":
    main()
