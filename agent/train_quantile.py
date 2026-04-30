"""
train_quantile.py
=================
Train three XGBoost quantile regression models (p10, p50, p90) to
produce calibrated 80% prediction intervals for crime counts.

Calibration check: across the validation set, ~80% of actual values
should fall within the predicted [p10, p90] interval. Empirical
coverage close to 80% means the intervals are honest.

Usage:
    python agent/train_quantile.py
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error

FEATURES_PATH = Path(__file__).parent / "data" / "features.parquet"
MODELS_DIR = Path(__file__).parent / "models"
PLOT_PATH = MODELS_DIR / "quantile_intervals_area25.png"

TRAIN_END = pd.to_datetime("2024-12-31").date()
VAL_END = pd.to_datetime("2025-06-30").date()

FEATURE_COLS = [
    "community_area",
    "lag_1", "lag_7", "lag_30",
    "rolling_7_mean", "rolling_30_mean",
    "day_of_week", "day_of_month", "month", "quarter",
    "year", "day_of_year",
    "is_weekend", "is_us_holiday",
]
TARGET_COL = "crime_count"

QUANTILES = [0.1, 0.5, 0.9]


def load_and_split(path: Path):
    print(f"Loading features from {path}...")
    df = pd.read_parquet(path)
    df["day"] = pd.to_datetime(df["day"]).dt.date
    df = df.sort_values(["community_area", "day"]).reset_index(drop=True)

    train = df[df["day"] <= TRAIN_END].copy()
    val = df[(df["day"] > TRAIN_END) & (df["day"] <= VAL_END)].copy()
    test = df[df["day"] > VAL_END].copy()

    print(f"  Train: {len(train):,}  Val: {len(val):,}  Test: {len(test):,}")
    return train, val, test


def train_quantile_model(X_train, y_train, X_val, y_val, alpha: float):
    """Train one XGBoost quantile regression model for a specific alpha."""
    print(f"\nTraining quantile model: alpha = {alpha}")
    model = xgb.XGBRegressor(
        objective="reg:quantileerror",
        quantile_alpha=alpha,
        n_estimators=500,
        max_depth=6,
        learning_rate=0.05,
        min_child_weight=3,
        subsample=0.8,
        colsample_bytree=0.8,
        tree_method="hist",
        early_stopping_rounds=20,
        random_state=42,
        verbosity=1,
    )
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        verbose=100,
    )
    print(f"  Best iteration: {model.best_iteration}")
    return model


def main() -> None:
    train, val, test = load_and_split(FEATURES_PATH)

    X_train = train[FEATURE_COLS]
    y_train = train[TARGET_COL]
    X_val = val[FEATURE_COLS]
    y_val = val[TARGET_COL].to_numpy()

    # Train one model per quantile.
    models = {}
    for alpha in QUANTILES:
        models[alpha] = train_quantile_model(X_train, y_train, X_val, y_val, alpha)

    # Predict each quantile on validation.
    preds = {alpha: models[alpha].predict(X_val) for alpha in QUANTILES}

    # ---------- Calibration check ----------
    p10 = preds[0.1]
    p50 = preds[0.5]
    p90 = preds[0.9]

    # An honest 80% interval: 80% of actuals should land in [p10, p90].
    in_interval = (y_val >= p10) & (y_val <= p90)
    empirical_coverage = float(in_interval.mean()) * 100

    # Median's MAE for comparison with point models.
    median_mae = mean_absolute_error(y_val, p50)

    # Average interval width (sanity: not collapsing to 0, not exploding).
    avg_width = float(np.mean(p90 - p10))

    # Crossing check: p10 should always <= p90. If not, model has issues.
    crossings = int(np.sum(p10 > p90))

    print("\n" + "=" * 60)
    print("VALIDATION METRICS — QUANTILE MODEL")
    print("=" * 60)
    print(f"Median (p50) MAE:               {median_mae:>8.3f}")
    print(f"Target 80% interval coverage:   80.00%")
    print(f"Empirical coverage [p10, p90]:  {empirical_coverage:>5.2f}%")
    print(f"Average interval width:         {avg_width:>8.3f}  crimes")
    print(f"Quantile crossings (p10 > p90): {crossings:>8}")

    if abs(empirical_coverage - 80.0) <= 5.0:
        print("\nCalibration: GOOD (within 5% of nominal 80%).")
    elif empirical_coverage > 80.0:
        print("\nCalibration: UNDERCONFIDENT (intervals too wide).")
    else:
        print("\nCalibration: OVERCONFIDENT (intervals too narrow).")

    # ---------- Save models ----------
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    for alpha, model in models.items():
        path = MODELS_DIR / f"xgboost_quantile_{int(alpha * 100):02d}.json"
        model.save_model(path)
        print(f"Saved {path.name}")

    # ---------- Visualization: actual vs interval for area 25 (Austin), validation period ----------
    val_a25 = val[val["community_area"] == 25].copy().reset_index(drop=True)
    if len(val_a25) > 0:
        idx_a25 = val.reset_index(drop=True).index[val.reset_index(drop=True)["community_area"] == 25]
        x = pd.to_datetime(val_a25["day"])
        actuals = val_a25[TARGET_COL].to_numpy()
        p10_a25 = p10[idx_a25]
        p50_a25 = p50[idx_a25]
        p90_a25 = p90[idx_a25]

        fig, ax = plt.subplots(figsize=(12, 5))
        ax.fill_between(x, p10_a25, p90_a25, alpha=0.3, label="80% interval [p10, p90]")
        ax.plot(x, p50_a25, color="tab:blue", linewidth=1.5, label="Median (p50)")
        ax.plot(x, actuals, color="black", linewidth=1, label="Actual", alpha=0.8)
        ax.set_title("Forecast intervals — Community Area 25 (Austin), validation period")
        ax.set_xlabel("Date")
        ax.set_ylabel("Daily crime count")
        ax.legend()
        fig.tight_layout()
        fig.savefig(PLOT_PATH, dpi=120)
        print(f"\nSaved interval plot to {PLOT_PATH}")


if __name__ == "__main__":
    main()