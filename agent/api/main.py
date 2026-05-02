from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
import sys
from pathlib import Path
import os
import psycopg
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from forecast import predict

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", "5432")),
    "dbname":   os.getenv("DB_NAME", "geocrime"),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}

app = FastAPI(title="GeoCrime Agent Tools API", version="0.3.0")

class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: str

class ForecastResponse(BaseModel):
    area: int
    date: str
    mean: float
    lower: float
    upper: float
    interval_width: float

class AreaCrimeResponse(BaseModel):
    community_area: int
    days: int
    total_crimes: int
    daily_average: float

class CrimePoint(BaseModel):
    case_number: str
    occurred_at: str
    primary_type: str
    lat: float
    lng: float

class RadiusResponse(BaseModel):
    lat: float
    lng: float
    radius_m: int
    count: int
    crimes: list[CrimePoint]

@app.get("/health", response_model=HealthResponse, tags=["meta"])
async def health():
    return HealthResponse(
        status="ok",
        service="geocrime-agent-tools",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

@app.get("/forecast/{community_area}/{date}", response_model=ForecastResponse, tags=["forecasting"])
async def forecast(community_area: int, date: str):
    try:
        result = predict(community_area=community_area, target_date=date)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Forecast failed: {e}")
    return ForecastResponse(**result)

@app.get("/crimes/area/{community_area}", response_model=AreaCrimeResponse, tags=["geospatial"])
async def crimes_by_area(community_area: int, days: int = Query(default=30, ge=1, le=365)):
    if not (1 <= community_area <= 77):
        raise HTTPException(status_code=422, detail="community_area must be 1-77")
    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COALESCE(SUM(crime_count), 0)
                    FROM daily_area_counts
                    WHERE community_area = %s
                      AND day >= CURRENT_DATE - %s::int
                """, (community_area, days))
                total = int(cur.fetchone()[0])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return AreaCrimeResponse(
        community_area=community_area,
        days=days,
        total_crimes=total,
        daily_average=round(total / days, 2),
    )

@app.get("/crimes/radius", response_model=RadiusResponse, tags=["geospatial"])
async def crimes_by_radius(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius_m: int = Query(default=500, ge=50, le=5000),
    limit: int = Query(default=50, ge=1, le=200),
):
    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT case_number,
                           occurred_at,
                           primary_type,
                           ST_Y(geom::geometry) AS lat,
                           ST_X(geom::geometry) AS lng
                    FROM crimes
                    WHERE geog IS NOT NULL
                      AND ST_DWithin(geog,
                            ST_MakePoint(%s, %s)::geography,
                            %s)
                    ORDER BY occurred_at DESC
                    LIMIT %s
                """, (lng, lat, radius_m, limit))
                rows = cur.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    crimes = [
        CrimePoint(
            case_number=r[0],
            occurred_at=r[1].isoformat(),
            primary_type=r[2],
            lat=round(r[3], 6),
            lng=round(r[4], 6),
        )
        for r in rows
    ]
    return RadiusResponse(lat=lat, lng=lng, radius_m=radius_m, count=len(crimes), crimes=crimes)
