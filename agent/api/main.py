from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Query
from fastapi import Path as ApiPath
from pydantic import BaseModel, Field
import sys
from pathlib import Path
import os
import psycopg
from dotenv import load_dotenv

from graph import run as agent_run

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

app = FastAPI(
    title="GeoCrime Agent Tools API",
    description=(
        "HTTP tools layer for the GeoCrime multi-agent decision-support system.\n\n"
        "## Endpoints\n"
        "- **meta** — liveness probe\n"
        "- **forecasting** — calibrated 80% prediction intervals per community area and date\n"
        "- **geospatial** — crime counts by area or within a radius\n\n"
        "Routing endpoint (Phase 3.4) deferred to Phase 5."
    ),
    version="0.3.0",
    contact={"name": "Hamza Asif", "url": "https://github.com/hamzawithpython/Geocrime"},
    license_info={"name": "MIT"},
)

class HealthResponse(BaseModel):
    status: str = Field(..., description="'ok' if healthy")
    service: str = Field(..., description="Service name")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp")

class ForecastResponse(BaseModel):
    area: int = Field(..., description="Community area code (1-77)")
    date: str = Field(..., description="Forecast date (YYYY-MM-DD)")
    mean: float = Field(..., description="Median forecast (p50)")
    lower: float = Field(..., description="Lower bound (p10)")
    upper: float = Field(..., description="Upper bound (p90)")
    interval_width: float = Field(..., description="p90 - p10")

class AreaCrimeResponse(BaseModel):
    community_area: int = Field(..., description="Community area code (1-77)")
    days: int = Field(..., description="Lookback window in days")
    total_crimes: int = Field(..., description="Total crimes in window")
    daily_average: float = Field(..., description="Mean daily crimes in window")

class CrimePoint(BaseModel):
    case_number: str = Field(..., description="CPD case number")
    occurred_at: str = Field(..., description="ISO 8601 timestamp")
    primary_type: str = Field(..., description="Crime type")
    lat: float = Field(..., description="Latitude")
    lng: float = Field(..., description="Longitude")

class RadiusResponse(BaseModel):
    lat: float = Field(..., description="Query latitude")
    lng: float = Field(..., description="Query longitude")
    radius_m: int = Field(..., description="Search radius in metres")
    count: int = Field(..., description="Number of crimes returned")
    crimes: list[CrimePoint] = Field(..., description="Crime records ordered by recency")


@app.get("/health", response_model=HealthResponse, tags=["meta"], summary="Liveness probe")
async def health():
    """Returns service status."""
    return HealthResponse(
        status="ok",
        service="geocrime-agent-tools",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/forecast/{community_area}/{date}", response_model=ForecastResponse,
         tags=["forecasting"], summary="Calibrated crime forecast for one area and date")
async def forecast(
    community_area: int = ApiPath(..., ge=1, le=77, description="Community area code (1-77)"),
    date: str = ApiPath(..., description="Target date YYYY-MM-DD"),
):
    """Returns calibrated 80% prediction interval. mean=p50, lower=p10, upper=p90."""
    try:
        result = predict(community_area=community_area, target_date=date)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Forecast failed: {e}")
    return ForecastResponse(**result)


@app.get("/crimes/area/{community_area}", response_model=AreaCrimeResponse,
         tags=["geospatial"], summary="Crime count for a community area over N days")
async def crimes_by_area(
    community_area: int = ApiPath(..., ge=1, le=77, description="Community area code (1-77)"),
    days: int = Query(default=30, ge=1, le=365, description="Lookback window in days"),
):
    """Returns total and average daily crime count for the area over the lookback window."""
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


@app.get("/crimes/radius", response_model=RadiusResponse,
         tags=["geospatial"], summary="Crimes within a radius of a coordinate")
async def crimes_by_radius(
    lat: float = Query(..., ge=-90, le=90, description="Centre latitude"),
    lng: float = Query(..., ge=-180, le=180, description="Centre longitude"),
    radius_m: int = Query(default=500, ge=50, le=5000, description="Search radius in metres"),
    limit: int = Query(default=50, ge=1, le=200, description="Max records to return"),
):
    """Returns most recent crimes within radius_m metres. Uses PostGIS ST_DWithin on geography index."""
    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT case_number, occurred_at, primary_type,
                           ST_Y(geom::geometry) AS lat,
                           ST_X(geom::geometry) AS lng
                    FROM crimes
                    WHERE geog IS NOT NULL
                      AND ST_DWithin(geog, ST_MakePoint(%s, %s)::geography, %s)
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

class ChatRequest(BaseModel):
    question: str = Field(..., description="Natural language question for the agent")


class ChatResponse(BaseModel):
    answer: str = Field(..., description="Agent's natural language answer")


@app.post("/chat", response_model=ChatResponse, tags=["agent"],
          summary="Ask the multi-agent system a natural language question")
async def chat(request: ChatRequest):
    """
    Runs the LangGraph agent with the given question.
    The agent decides which tools to call and returns a synthesized answer.
    """
    try:
        answer = agent_run(request.question)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")
    return ChatResponse(answer=answer)