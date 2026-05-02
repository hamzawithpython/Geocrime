"""
Geospatial agent tools.
Calls the /crimes/area and /crimes/radius endpoints.
"""

import httpx
from langchain_core.tools import tool
import os
API_BASE = os.getenv("API_BASE", "http://localhost:8000")


@tool
def crimes_by_area(community_area: int, days: int = 30) -> dict:
    """
    Get total and average daily crime count for a Chicago community area.

    Args:
        community_area: int 1-77 (Chicago community area code)
        days: lookback window in days (default 30, max 365)
    """
    response = httpx.get(
        f"{API_BASE}/crimes/area/{community_area}",
        params={"days": days},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


@tool
def crimes_by_radius(lat: float, lng: float, radius_m: int = 500) -> dict:
    """
    Get most recent crimes within a radius of a coordinate.

    Args:
        lat: latitude of the centre point
        lng: longitude of the centre point
        radius_m: search radius in metres (default 500, max 5000)
    """
    response = httpx.get(
        f"{API_BASE}/crimes/radius",
        params={"lat": lat, "lng": lng, "radius_m": radius_m},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()