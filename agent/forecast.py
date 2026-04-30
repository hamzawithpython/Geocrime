"""
forecast.py
===========
Inference module for the crime forecasting subsystem.

Exposes a single function `predict(community_area, target_date)` that
returns calibrated forecast intervals using the three quantile models
trained in Phase 2.5.

At inference time, lag and rolling features are computed by querying
PostGIS for the area's recent history.

Usage (programmatic):
    from agent.forecast import predict
    result = predict(community_area=25, target_date="2025-08-15")
    # {"area": 25, "date": "2025-08-15", "mean": 30.4,
    #  "lower": 24.1, "upper": 36.8}

Usage (CLI):
    python agent/forecast.py 25 2025-08-15
"""

import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import holidays
import numpy as np
import pandas as pd
import psycopg
import xgboost as xgb
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", "5432")),
    "dbname":   os.getenv("DB_NAME", "geocrime"),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}

MODELS_DIR = Path(__file__).parent / "models"

FEATURE_COLS = [
    "community_area",
    "lag_1", "lag_7", "lag_30",
    "rolling_7_mean", "rolling_30_mean",
    "day_of_week", "day_of_month", "month", "quarter",
    "year", "day_of_year",
    "is_weekend", "is_us_holiday",
]


# =============================================================
# Lazy model loading — load once, cache
# =============================================================

_models: dict[str, xgb.XGBRegressor] | None = None


def _load_models() -> dict[str, xgb.XGBRegressor]:
    """Load the three quantile models from disk; cache for repeat calls."""
    global _models
    if _models is not None:
        return _models

    _models = {}
    for alpha_pct in (10, 50, 90):
        path = MODELS_DIR / f"xgboost_quantile_{alpha_pct:02d}.json"
        if not path.exists():
            raise FileNotFoundError(
                f"Model file missing: {path}. Run train_quantile.py first."
            )
        m = xgb.XGBRegressor()
        m.load_model(path)
        _models[f"p{alpha_pct}"] = m
    return _models


# =============================================================
# Feature construction at inference time
# =============================================================

def _fetch_history(area: int, target_date: date) -> pd.DataFrame:
    """Pull the last ~31 days of (day, crime_count) for this area, ending the
    day BEFORE target_date. Used to compute lag and rolling features.

    Returns at most 31 rows. May return fewer if data is missing — caller
    must handle that case.
    """
    start = target_date - timedelta(days=31)
    end = target_date - timedelta(days=1)
    with psycopg.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT day, crime_count
                FROM daily_area_counts
                WHERE community_area = %s
                  AND day BETWEEN %s AND %s
                ORDER BY day
                """,
                (area, start, end),
            )
            rows = cur.fetchall()
    if not rows:
        return pd.DataFrame(columns=["day", "crime_count"])
    df = pd.DataFrame(rows, columns=["day", "crime_count"])
    df["day"] = pd.to_datetime(df["day"]).dt.date
    return df


def _build_features(area: int, target_date: date) -> pd.DataFrame:
    """Build a single-row feature DataFrame for (area, target_date).

    Lag and rolling features come from PostGIS history. Temporal features
    come from target_date directly.
    """
    history = _fetch_history(area, target_date)

    # Build a complete date range; missing days are zero-crime (matches
    # the zero-fill logic in build_features.py).
    all_days = pd.date_range(
        target_date - timedelta(days=31),
        target_date - timedelta(days=1),
        freq="D",
    ).date
    full = pd.DataFrame({"day": all_days})
    full = full.merge(history, on="day", how="left").fillna({"crime_count": 0})
    full = full.sort_values("day").reset_index(drop=True)

    counts = full["crime_count"].to_numpy()

    # Lags relative to target_date (last row of `full` is target_date - 1 day).
    lag_1 = float(counts[-1])
    lag_7 = float(counts[-7]) if len(counts) >= 7 else float(counts[0])
    lag_30 = float(counts[-30]) if len(counts) >= 30 else float(counts[0])

    # Rolling means: prior 7 days and prior 30 days, ending yesterday.
    rolling_7 = float(np.mean(counts[-7:])) if len(counts) >= 7 else float(np.mean(counts))
    rolling_30 = float(np.mean(counts[-30:])) if len(counts) >= 30 else float(np.mean(counts))

    # Temporal features.
    target_dt = pd.Timestamp(target_date)
    years = [target_dt.year]
    us_holidays = holidays.UnitedStates(years=years)

    row = {
        "community_area":   area,
        "lag_1":            lag_1,
        "lag_7":            lag_7,
        "lag_30":           lag_30,
        "rolling_7_mean":   rolling_7,
        "rolling_30_mean":  rolling_30,
        "day_of_week":      target_dt.dayofweek,
        "day_of_month":     target_dt.day,
        "month":            target_dt.month,
        "quarter":          target_dt.quarter,
        "year":             target_dt.year,
        "day_of_year":      target_dt.dayofyear,
        "is_weekend":       int(target_dt.dayofweek >= 5),
        "is_us_holiday":    int(target_date in us_holidays),
    }
    return pd.DataFrame([row], columns=FEATURE_COLS)


# =============================================================
# Public API
# =============================================================

def predict(community_area: int, target_date) -> dict:
    """Forecast daily crime count for one (area, date).

    Args:
        community_area: int, 1-77 (Chicago community area code).
        target_date: date object or "YYYY-MM-DD" string.

    Returns:
        dict with keys: area, date, mean (median forecast),
        lower (p10), upper (p90), interval_width.
    """
    if isinstance(target_date, str):
        target_date = datetime.strptime(target_date, "%Y-%m-%d").date()

    if not (1 <= community_area <= 77):
        raise ValueError(f"community_area must be 1-77, got {community_area}")

    models = _load_models()
    X = _build_features(community_area, target_date)

    # Clip negative predictions to 0 — crime counts can't be negative.
    p10 = max(0.0, float(models["p10"].predict(X)[0]))
    p50 = max(0.0, float(models["p50"].predict(X)[0]))
    p90 = max(0.0, float(models["p90"].predict(X)[0]))

    return {
        "area":            community_area,
        "date":            target_date.isoformat(),
        "mean":            round(p50, 2),
        "lower":           round(p10, 2),
        "upper":           round(p90, 2),
        "interval_width":  round(p90 - p10, 2),
    }


# =============================================================
# CLI
# =============================================================

def _cli() -> None:
    if len(sys.argv) != 3:
        sys.exit("Usage: python agent/forecast.py <community_area> <YYYY-MM-DD>")
    area = int(sys.argv[1])
    target_date = sys.argv[2]
    result = predict(area, target_date)
    print(f"\nForecast for community area {result['area']} on {result['date']}:")
    print(f"  Median forecast:    {result['mean']:>6.2f} crimes")
    print(f"  80% interval:       [{result['lower']:.2f}, {result['upper']:.2f}]")
    print(f"  Interval width:     {result['interval_width']:>6.2f}")


if __name__ == "__main__":
    _cli()