"""Unit tests for pure metric helpers and the reliability score formula.

Run with:  pytest tests/test_metrics.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from build_flight_reliability import _binary, _percentile, _rate, add_row, new_stats, stats_metrics
from config import (
    SCORE_WEIGHT_ARRIVAL_DELAY,
    SCORE_WEIGHT_CANCELLATION,
    SCORE_WEIGHT_DIVERSION,
    SCORE_WEIGHT_SEVERE_DELAY,
)


# ---------------------------------------------------------------------------
# _binary
# ---------------------------------------------------------------------------

def test_binary_one():
    assert _binary("1") == 1
    assert _binary("1.0") == 1


def test_binary_zero():
    assert _binary("0") == 0
    assert _binary("0.0") == 0


def test_binary_null():
    assert _binary(None) == 0
    assert _binary("") == 0


# ---------------------------------------------------------------------------
# _rate
# ---------------------------------------------------------------------------

def test_rate_basic():
    assert _rate(3, 10) == 0.3


def test_rate_zero_denominator():
    assert _rate(5, 0) == 0.0


# ---------------------------------------------------------------------------
# _percentile
# ---------------------------------------------------------------------------

def test_percentile_empty():
    assert _percentile([], 0.9) == 0.0


def test_percentile_p50():
    assert _percentile([1, 2, 3, 4, 5], 0.5) == 3


def test_percentile_p100():
    assert _percentile([10, 20, 30], 1.0) == 30


# ---------------------------------------------------------------------------
# Reliability score formula
# Weights from config must match macros/reliability_score.sql.
# ---------------------------------------------------------------------------

def test_score_perfect_airline():
    stats = new_stats()
    # 100 flights, zero bad events
    for _ in range(100):
        add_row(stats, {
            "ArrDelayMinutes": "0",
            "Distance": "500",
            "ArrDel15": "0",
            "DepDel15": "0",
            "Cancelled": "0",
            "Diverted": "0",
        })
    metrics = stats_metrics(stats)
    assert metrics["reliability_score"] == 100.0


def test_score_all_cancelled():
    stats = new_stats()
    for _ in range(100):
        add_row(stats, {
            "ArrDelayMinutes": "",
            "Distance": "500",
            "ArrDel15": "0",
            "DepDel15": "0",
            "Cancelled": "1",
            "Diverted": "0",
        })
    metrics = stats_metrics(stats)
    # 100% cancellation → score = max(0, 100 - 45*1) = 55
    expected = max(0, 100 - SCORE_WEIGHT_CANCELLATION * 1.0)
    assert metrics["reliability_score"] == round(expected, 2)


def test_score_clamped_at_zero():
    """Pathological airline with 100% cancellations + 100% diversions should not go below 0."""
    stats = new_stats()
    for _ in range(100):
        add_row(stats, {
            "ArrDelayMinutes": "300",
            "Distance": "500",
            "ArrDel15": "1",
            "DepDel15": "1",
            "Cancelled": "1",
            "Diverted": "1",
        })
    metrics = stats_metrics(stats)
    assert metrics["reliability_score"] >= 0


def test_score_weights_sum_to_100():
    """Confirm the weight contract: full penalty on every dimension hits 0, not below."""
    total_penalty = (
        SCORE_WEIGHT_CANCELLATION
        + SCORE_WEIGHT_DIVERSION
        + SCORE_WEIGHT_ARRIVAL_DELAY
        + SCORE_WEIGHT_SEVERE_DELAY
    )
    assert total_penalty == 100
