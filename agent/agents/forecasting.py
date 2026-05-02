"""
Forecasting agent tool.
Calls the /forecast endpoint and returns calibrated prediction intervals.
"""

import httpx
from langchain_core.tools import tool
import os
API_BASE = os.getenv("API_BASE", "http://localhost:8000")


@tool
def forecast_crime(community_area: int, date: str) -> dict:
    """
    Forecast daily crime count for a Chicago community area on a given date.
    Returns median forecast and 80% prediction interval (lower/upper).

    Args:
        community_area: int 1-77 (Chicago community area code)
        date: target date in YYYY-MM-DD format
    """
    response = httpx.get(f"{API_BASE}/forecast/{community_area}/{date}", timeout=10)
    response.raise_for_status()
    return response.json()