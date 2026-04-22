"""
ingest_crimes.py
================
Stream the Chicago crime CSV into PostGIS in batches.

Usage:
    python agent/ingest_crimes.py agent/data/chicago_crimes_2020_present.csv

Reads the CSV row by row (memory-safe), validates each record, builds a
PostGIS point geometry from latitude/longitude, and inserts in batches
of 1000 for performance.

Records with missing/invalid lat/lon are inserted with NULL geom.
Records with missing required fields (id, date, primary_type) are skipped.
"""

import csv
import os
import sys
from datetime import datetime
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from tqdm import tqdm

# Load DB credentials from agent/.env
load_dotenv(Path(__file__).parent / ".env")

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", "5432")),
    "dbname":   os.getenv("DB_NAME", "geocrime"),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}

BATCH_SIZE = 1000

INSERT_SQL = """
    INSERT INTO crimes (
        id, case_number, occurred_at, primary_type, description,
        location_description, arrest, domestic, community_area, district, geom
    ) VALUES (
        %(id)s, %(case_number)s, %(occurred_at)s, %(primary_type)s, %(description)s,
        %(location_description)s, %(arrest)s, %(domestic)s, %(community_area)s, %(district)s,
        CASE
            WHEN %(lon)s::float8 IS NULL OR %(lat)s::float8 IS NULL THEN NULL
            ELSE ST_SetSRID(ST_MakePoint(%(lon)s::float8, %(lat)s::float8), 4326)
        END
    )
    ON CONFLICT (id) DO NOTHING
"""


def parse_row(row: dict) -> dict | None:
    """Convert a CSV row (all strings) into typed values for INSERT.

    Returns None if required fields are missing/invalid.
    """
    try:
        record_id = int(row["id"])
        primary_type = row["primary_type"].strip()
        date_str = row["date"]
        if not record_id or not primary_type or not date_str:
            return None

        occurred_at = datetime.fromisoformat(date_str)
    except (ValueError, KeyError):
        return None

    # Optional fields
    def to_float(s):
        try:
            return float(s) if s else None
        except ValueError:
            return None

    def to_int(s):
        try:
            return int(s) if s else None
        except ValueError:
            return None

    def to_bool(s):
        return s.lower() == "true" if s else False

    return {
        "id":                   record_id,
        "case_number":          row.get("case_number") or None,
        "occurred_at":          occurred_at,
        "primary_type":         primary_type,
        "description":          row.get("description") or None,
        "location_description": row.get("location_description") or None,
        "arrest":               to_bool(row.get("arrest", "")),
        "domestic":             to_bool(row.get("domestic", "")),
        "community_area":       to_int(row.get("community_area", "")),
        "district":             to_int(row.get("district", "")),
        "lat":                  to_float(row.get("latitude", "")),
        "lon":                  to_float(row.get("longitude", "")),
    }


def main(csv_path: str) -> None:
    csv_file = Path(csv_path)
    if not csv_file.exists():
        sys.exit(f"ERROR: CSV file not found at {csv_path}")

    print(f"Reading: {csv_file}")
    print(f"Connecting to PostGIS at {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}")

    # Counters
    rows_read = 0
    rows_inserted = 0
    rows_skipped = 0
    rows_no_geom = 0

    with psycopg.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            with open(csv_file, "r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                batch = []

                for row in tqdm(reader, desc="Ingesting", unit="rows"):
                    rows_read += 1
                    parsed = parse_row(row)

                    if parsed is None:
                        rows_skipped += 1
                        continue

                    if parsed["lat"] is None or parsed["lon"] is None:
                        rows_no_geom += 1

                    batch.append(parsed)

                    if len(batch) >= BATCH_SIZE:
                        cur.executemany(INSERT_SQL, batch)
                        rows_inserted += len(batch)
                        batch = []

                # Flush remaining batch
                if batch:
                    cur.executemany(INSERT_SQL, batch)
                    rows_inserted += len(batch)

        conn.commit()

    print()
    print(f"Total rows read:          {rows_read:>10,}")
    print(f"Rows inserted:            {rows_inserted:>10,}")
    print(f"Rows skipped (bad data):  {rows_skipped:>10,}")
    print(f"Rows with NULL geom:      {rows_no_geom:>10,}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python ingest_crimes.py <path-to-csv>")
    main(sys.argv[1])