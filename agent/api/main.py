from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from forecast import predict

app = FastAPI(title="GeoCrime Agent Tools API", version="0.2.0")

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
