"""
train_xgboost.py
================
Train an XGBoost regression model to predict daily crime counts per
community area. Compare against Phase 2.3 baselines.

Usage:
    python agent/train_xgboost.py
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error

FEATURES_PATH = Path(__file__).parent / "data" / "features.parquet"
MODEL_PATH = Path(__file__).parent / "models" / "xgboost_baseline.json"
PLOT_PATH = Path(__file__).parent / "models" / "feature_importance.png"

# Same temporal cutoffs as Phase 2.3 — must match exactly.
TRAIN_END = pd.to_datetime("2024-12-31").date()
VAL_END = pd.to_datetime("2025-06-30").date()

# Features to use (everything except identifier and target).
FEATURE_COLS = [
    "community_area",
    "lag_1", "lag_7", "lag_30",
    "rolling_7_mean", "rolling_30_mean",
    "day_of_week", "day_of_month", "month", "quarter",
    "year", "day_of_year",
    "is_weekend", "is_us_holiday",
]
TARGET_COL = "crime_count"


def load_and_split(path: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load parquet and apply the same temporal split as the baselines."""
    print(f"Loading features from {path}...")
    df = pd.read_parquet(path)
    df["day"] = pd.to_datetime(df["day"]).dt.date
    df = df.sort_values(["community_area", "day"]).reset_index(drop=True)

    train = df[df["day"] <= TRAIN_END].copy()
    val = df[(df["day"] > TRAIN_END) & (df["day"] <= VAL_END)].copy()
    test = df[df["day"] > VAL_END].copy()

    print(f"  Train: {len(train):,}  Val: {len(val):,}  Test: {len(test):,}")
    return train, val, test


def mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Mean absolute percentage error, ignoring zero ground truth."""
    mask = y_true != 0
    if mask.sum() == 0:
        return float("nan")
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


def main() -> None:
    train, val, test = load_and_split(FEATURES_PATH)

    X_train = train[FEATURE_COLS]
    y_train = train[TARGET_COL]
    X_val = val[FEATURE_COLS]
    y_val = val[TARGET_COL]

    print("\nTraining XGBoost...")
    model = xgb.XGBRegressor(
        # Sensible defaults; we can tune later if needed.
        n_estimators=500,
        max_depth=6,
        learning_rate=0.05,
        min_child_weight=3,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="reg:squarederror",
        tree_method="hist",
        early_stopping_rounds=20,
        random_state=42,
        verbosity=1,
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_train, y_train), (X_val, y_val)],
        verbose=50,  # print progress every 50 rounds
    )

    print(f"\nBest iteration: {model.best_iteration}")
    print(f"Best validation RMSE: {model.best_score:.4f}")

    # Evaluate on validation (in same metrics as baselines).
    y_pred = model.predict(X_val)
    val_mae = mean_absolute_error(y_val, y_pred)
    val_rmse = np.sqrt(mean_squared_error(y_val, y_pred))
    val_mape = mape(y_val.to_numpy(), y_pred)

    print("\n" + "=" * 60)
    print("VALIDATION METRICS")
    print("=" * 60)
    print(f"{'Model':<32} {'MAE':>8} {'RMSE':>8} {'MAPE %':>8}")
    print("-" * 60)
    print(f"{'Historical mean (Phase 2.3)':<32} {2.444:>8.3f} {3.425:>8.3f} {45.32:>8.2f}")
    print(f"{'Naive lag (Phase 2.3)':<32} {3.154:>8.3f} {4.421:>8.3f} {57.91:>8.2f}")
    print(f"{'Rolling 7-day (Phase 2.3)':<32} {2.465:>8.3f} {3.428:>8.3f} {45.88:>8.2f}")
    print(f"{'XGBoost':<32} {val_mae:>8.3f} {val_rmse:>8.3f} {val_mape:>8.2f}")

    improvement = (2.444 - val_mae) / 2.444 * 100
    print(f"\nMAE improvement vs best baseline: {improvement:+.1f}%")

    # Feature importance.
    print("\nFeature importance (gain):")
    importance = model.get_booster().get_score(importance_type="gain")
    sorted_imp = sorted(importance.items(), key=lambda x: x[1], reverse=True)
    for feat, gain in sorted_imp:
        print(f"  {feat:<25} {gain:>10.2f}")

    # Save model and importance plot.
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(MODEL_PATH)
    print(f"\nModel saved to {MODEL_PATH}")

    fig, ax = plt.subplots(figsize=(8, 5))
    feats, gains = zip(*sorted_imp)
    ax.barh(feats[::-1], gains[::-1])
    ax.set_xlabel("Importance (gain)")
    ax.set_title("XGBoost Feature Importance")
    fig.tight_layout()
    fig.savefig(PLOT_PATH, dpi=120)
    print(f"Feature importance plot saved to {PLOT_PATH}")


if __name__ == "__main__":
    main()