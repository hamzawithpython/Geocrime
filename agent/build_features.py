"""
build_features.py
=================
Build the feature matrix for the forecasting model.

Reads aggregates from PostGIS (daily_area_counts materialized view),
fills missing (area, day) combinations with zero, computes lag and
rolling features, adds temporal features, and writes the result as
a parquet file for Phase 2.3 (training).

Usage:
    python agent/build_features.py
"""

import os
from pathlib import Path

import warnings
warnings.filterwarnings("ignore", message=".*pandas only supports SQLAlchemy.*")

import holidays
import numpy as np
import pandas as pd
import psycopg
from dotenv import load_dotenv

# Load DB credentials
load_dotenv(Path(__file__).parent / ".env")

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", "5432")),
    "dbname":   os.getenv("DB_NAME", "geocrime"),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}

OUTPUT_PATH = Path(__file__).parent / "data" / "features.parquet"


def load_aggregates() -> pd.DataFrame:
    """Load (community_area, day, crime_count) from PostGIS."""
    print("Loading aggregates from PostGIS...")
    with psycopg.connect(**DB_CONFIG) as conn:
        df = pd.read_sql(
            "SELECT community_area, day, crime_count FROM daily_area_counts",
            conn,
        )
    print(f"  Loaded {len(df):,} rows covering {df['day'].nunique()} days, "
          f"{df['community_area'].nunique()} areas.")
    return df


def build_complete_grid(df: pd.DataFrame) -> pd.DataFrame:
    """Build a complete (area, day) grid with zero-fill for missing combinations."""
    print("Building complete (area, day) grid...")

    areas = sorted(df["community_area"].unique())
    days = pd.date_range(df["day"].min(), df["day"].max(), freq="D")
    print(f"  Grid dimensions: {len(areas)} areas × {len(days)} days = {len(areas) * len(days):,} cells")

    # Cartesian product
    grid = pd.MultiIndex.from_product(
        [areas, days],
        names=["community_area", "day"],
    ).to_frame(index=False)
    # Normalize day types for merging
    grid["day"] = pd.to_datetime(grid["day"]).dt.date
    df["day"] = pd.to_datetime(df["day"]).dt.date

    # Left-join aggregates onto grid, zero-fill missing
    complete = grid.merge(df, on=["community_area", "day"], how="left")
    n_before = complete["crime_count"].notna().sum()
    complete["crime_count"] = complete["crime_count"].fillna(0).astype(int)
    n_zeros = (complete["crime_count"] == 0).sum()

    print(f"  Filled {len(complete) - n_before:,} missing cells with zero.")
    print(f"  Total zero-crime (area, day) cells: {n_zeros:,} ({n_zeros / len(complete) * 100:.1f}%)")

    return complete

def add_lag_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add lag and rolling-window features.

    IMPORTANT: Sorted by (community_area, day) and operations are grouped
    by area — otherwise values bleed across areas. Rolling features use
    shift(1) first to avoid leaking today's value into today's average.
    """
    print("Adding lag and rolling features...")

    # Critical: sort for correct shift operations.
    df = df.sort_values(["community_area", "day"]).reset_index(drop=True)

    grp = df.groupby("community_area")["crime_count"]

    # Lag features — what was the crime count N days ago in this area?
    df["lag_1"] = grp.shift(1)
    df["lag_7"] = grp.shift(7)
    df["lag_30"] = grp.shift(30)

    # Rolling averages — ending YESTERDAY (shift(1) first to exclude today).
    # Use groupby+transform to keep grouping context through the rolling window;
    # otherwise rolling bleeds across community area boundaries.
    df["rolling_7_mean"] = (
        df.groupby("community_area")["crime_count"]
          .transform(lambda x: x.shift(1).rolling(window=7, min_periods=1).mean())
    )
    df["rolling_30_mean"] = (
        df.groupby("community_area")["crime_count"]
          .transform(lambda x: x.shift(1).rolling(window=30, min_periods=1).mean())
    )

    # Count NaNs by feature — lag_30 has the most because it needs 30 days of history.
    nan_counts = df[["lag_1", "lag_7", "lag_30", "rolling_7_mean", "rolling_30_mean"]].isna().sum()
    print(f"  NaN counts by feature:")
    for feature, count in nan_counts.items():
        print(f"    {feature:20s} {count:>6,}")

    return df

def add_temporal_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add calendar features derived from the day column.

    Tree-based models like XGBoost can use these integer-encoded
    categoricals directly without one-hot expansion.
    """
    print("Adding temporal features...")

    # Ensure day is datetime for .dt accessor.
    day_dt = pd.to_datetime(df["day"])

    df["day_of_week"]  = day_dt.dt.dayofweek.astype("int8")     # 0=Mon, 6=Sun
    df["day_of_month"] = day_dt.dt.day.astype("int8")
    df["month"]        = day_dt.dt.month.astype("int8")
    df["quarter"]      = day_dt.dt.quarter.astype("int8")
    df["year"]         = day_dt.dt.year.astype("int16")
    df["day_of_year"]  = day_dt.dt.dayofyear.astype("int16")
    df["is_weekend"]   = (day_dt.dt.dayofweek >= 5).astype("int8")

    # US federal holidays for our date range.
    years = sorted(day_dt.dt.year.unique())
    us_holidays = holidays.UnitedStates(years=years)
    df["is_us_holiday"] = day_dt.dt.date.isin(us_holidays).astype("int8")

    n_holidays = df["is_us_holiday"].sum()
    n_weekend = df["is_weekend"].sum()
    print(f"  Weekend rows: {n_weekend:,} ({n_weekend / len(df) * 100:.1f}%)")
    print(f"  Holiday rows: {n_holidays:,} ({n_holidays / len(df) * 100:.1f}%)")

    return df

def save_features(df: pd.DataFrame, path: Path) -> None:
    """Drop rows with NaN lag values and save the feature matrix as parquet."""
    print("Saving features...")

    # Drop rows where lag features are still NaN — the first 30 days
    # of each area can't be used for training.
    n_before = len(df)
    df_clean = df.dropna(subset=["lag_1", "lag_7", "lag_30"]).reset_index(drop=True)
    n_dropped = n_before - len(df_clean)

    print(f"  Dropped {n_dropped:,} rows with NaN lag values "
          f"({n_dropped / n_before * 100:.1f}% of data, expected ~1.3%).")

    path.parent.mkdir(parents=True, exist_ok=True)
    df_clean.to_parquet(path, engine="pyarrow", compression="snappy", index=False)

    size_mb = path.stat().st_size / (1024 * 1024)
    print(f"  Wrote {len(df_clean):,} rows × {len(df_clean.columns)} cols to {path}")
    print(f"  File size: {size_mb:.2f} MB")

def main() -> None:
    df_raw = load_aggregates()
    df_grid = build_complete_grid(df_raw)
    df_lag = add_lag_features(df_grid)
    df_temporal = add_temporal_features(df_lag)
    save_features(df_temporal, OUTPUT_PATH)

    print("\nDone.")


if __name__ == "__main__":
    main()