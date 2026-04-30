"""
train_baseline.py
=================
Temporal train/val/test split + three baseline models.

Establishes the performance floor that the XGBoost model (Phase 2.4)
must beat. Reports MAE, RMSE, MAPE for each baseline on the
validation set.

Usage:
    python agent/train_baseline.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

FEATURES_PATH = Path(__file__).parent / "data" / "features.parquet"

# Temporal cutoffs — discussed in Phase 2.0 plan.
TRAIN_END = pd.to_datetime("2024-12-31").date()
VAL_END = pd.to_datetime("2025-06-30").date()
# Test set is everything after VAL_END.


# =============================================================
# Metrics
# =============================================================

def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_true - y_pred)))


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Mean absolute percentage error.

    Skips rows where y_true == 0 to avoid division by zero. This means
    the metric is only defined over non-zero ground truth — appropriate
    for our use case (zero-crime days are not the interesting prediction).
    """
    mask = y_true != 0
    if mask.sum() == 0:
        return float("nan")
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


# =============================================================
# Data loading + split
# =============================================================

def load_and_split(path: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load parquet and apply temporal split."""
    print(f"Loading features from {path}...")
    df = pd.read_parquet(path)
    df["day"] = pd.to_datetime(df["day"]).dt.date  # ensure consistent date type
    df = df.sort_values(["community_area", "day"]).reset_index(drop=True)

    train = df[df["day"] <= TRAIN_END].copy()
    val = df[(df["day"] > TRAIN_END) & (df["day"] <= VAL_END)].copy()
    test = df[df["day"] > VAL_END].copy()

    print(f"  Train:      {len(train):>7,} rows  ({train['day'].min()} to {train['day'].max()})")
    print(f"  Validation: {len(val):>7,} rows  ({val['day'].min()} to {val['day'].max()})")
    print(f"  Test:       {len(test):>7,} rows  ({test['day'].min()} to {test['day'].max()})")

    # Sanity: total should equal the input.
    assert len(train) + len(val) + len(test) == len(df), "Split row counts don't sum"

    return train, val, test


# =============================================================
# Baselines
# =============================================================

def baseline_historical_mean(train: pd.DataFrame, val: pd.DataFrame) -> np.ndarray:
    """Predict each area's training-set mean crime count."""
    area_means = train.groupby("community_area")["crime_count"].mean()
    return val["community_area"].map(area_means).fillna(area_means.mean()).to_numpy()


def baseline_naive_lag(val: pd.DataFrame) -> np.ndarray:
    """Predict lag_1 (yesterday's count)."""
    return val["lag_1"].to_numpy()


def baseline_rolling_7(val: pd.DataFrame) -> np.ndarray:
    """Predict the 7-day rolling mean."""
    return val["rolling_7_mean"].to_numpy()


# =============================================================
# Main
# =============================================================

def main() -> None:
    train, val, test = load_and_split(FEATURES_PATH)
    y_val = val["crime_count"].to_numpy()

    print("\nEvaluating baselines on validation set...")
    baselines = {
        "Historical mean (per area)": baseline_historical_mean(train, val),
        "Naive lag (yesterday)":      baseline_naive_lag(val),
        "Rolling 7-day mean":         baseline_rolling_7(val),
    }

    # Report
    print(f"\n{'Baseline':<32} {'MAE':>8} {'RMSE':>8} {'MAPE %':>8}")
    print("-" * 60)
    for name, y_pred in baselines.items():
        print(f"{name:<32} {mae(y_val, y_pred):>8.3f} {rmse(y_val, y_pred):>8.3f} {mape(y_val, y_pred):>8.2f}")

    print("\nThese are the bars the XGBoost model must beat in Phase 2.4.")


if __name__ == "__main__":
    main()