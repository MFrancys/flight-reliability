from __future__ import annotations

# Date range for the local portfolio dataset.
YEARS: list[int] = [2019]
MONTHS: list[int] = [1, 2, 3]

# Reliability score penalty weights — must match macros/reliability_score.sql.
SCORE_WEIGHT_CANCELLATION = 45
SCORE_WEIGHT_DIVERSION = 30
SCORE_WEIGHT_ARRIVAL_DELAY = 20
SCORE_WEIGHT_SEVERE_DELAY = 5
