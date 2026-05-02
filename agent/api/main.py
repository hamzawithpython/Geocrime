"""
agent.api.main
==============
FastAPI application exposing the agent system's tool endpoints.

Currently provides only a health check (Phase 3.1). Phase 3.2+ will
add forecasting, geospatial, and routing endpoints.

Run locally:
    uvicorn agent.api.main:app --reload --port 8000

Then visit:
    http://localhost:8000/health      # health check
    http://localhost:8000/docs        # auto-generated interactive docs
    http://localhost:8000/openapi.json  # OpenAPI schema
"""

from datetime import datetime, timezone

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(
    title="GeoCrime Agent Tools API",
    description=(
        "HTTP tools layer for the GeoCrime multi-agent decision-support "
        "system. Each endpoint exposes one capability used by the supervisor "
        "agent in Phase 4."
    ),
    version="0.1.0",
)


# =============================================================
# Response models — Pydantic gives us validation + OpenAPI schema for free
# =============================================================

class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Service status, 'ok' if healthy.")
    service: str = Field(..., description="Service name.")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp of the response.")


# =============================================================
# Endpoints
# =============================================================

@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health check",
    tags=["meta"],
)
async def health() -> HealthResponse:
    """Return service status. Used for liveness probes and integration tests."""
    return HealthResponse(
        status="ok",
        service="geocrime-agent-tools",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )