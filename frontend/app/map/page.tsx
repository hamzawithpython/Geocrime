"use client";

import { useState, useCallback, useRef } from "react";
import Map, { Marker, Source, Layer, NavigationControl } from "react-map-gl";
import type { LayerProps } from "react-map-gl";
import "mapbox-gl/dist/mapbox-gl.css";

const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN!;
const DJANGO_URL = process.env.NEXT_PUBLIC_DJANGO_URL || "http://localhost:8080";

interface Point {
  lat: number;
  lng: number;
}

interface RouteResult {
  route: [number, number][];
  safety_info: { total_crime_score: number };
}

export default function MapPage() {
  const [origin, setOrigin] = useState<Point | null>(null);
  const [destination, setDestination] = useState<Point | null>(null);
  const [route, setRoute] = useState<RouteResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectingFor, setSelectingFor] = useState<"origin" | "destination">("origin");

  const handleMapClick = useCallback(
    (e: { lngLat: { lat: number; lng: number } }) => {
      const point = { lat: e.lngLat.lat, lng: e.lngLat.lng };
      if (selectingFor === "origin") {
        setOrigin(point);
        setSelectingFor("destination");
      } else {
        setDestination(point);
        setSelectingFor("origin");
      }
      setRoute(null);
      setError(null);
    },
    [selectingFor]
  );

  const getRoute = async () => {
    if (!origin || !destination) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${DJANGO_URL}/api/custom-route/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ origin, destination }),
      });
      const data = await res.json();
      if (!data.ok) {
        setError(data.message);
      } else {
        setRoute(data);
      }
    } catch {
      setError("Failed to connect to routing server.");
    } finally {
      setLoading(false);
    }
  };

  const clearAll = () => {
    setOrigin(null);
    setDestination(null);
    setRoute(null);
    setError(null);
    setSelectingFor("origin");
  };

  const routeGeoJSON = route
    ? {
        type: "Feature" as const,
        geometry: {
          type: "LineString" as const,
          coordinates: route.route.map(([lat, lng]) => [lng, lat]),
        },
        properties: {},
      }
    : null;

  const routeLayerStyle: LayerProps = {
    id: "route",
    type: "line",
    paint: {
      "line-color": "#3b82f6",
      "line-width": 4,
      "line-opacity": 0.8,
    },
  };

  return (
    <div className="relative w-full h-full">
      <Map
        initialViewState={{
          longitude: -87.6298,
          latitude: 41.8781,
          zoom: 11,
        }}
        style={{ width: "100%", height: "100%" }}
        mapStyle="mapbox://styles/mapbox/dark-v11"
        mapboxAccessToken={MAPBOX_TOKEN}
        onClick={handleMapClick}
        cursor="crosshair"
      >
        <NavigationControl position="top-right" />

        {origin && (
          <Marker longitude={origin.lng} latitude={origin.lat} color="#22c55e" />
        )}
        {destination && (
          <Marker longitude={destination.lng} latitude={destination.lat} color="#ef4444" />
        )}

        {routeGeoJSON && (
          <Source id="route" type="geojson" data={routeGeoJSON}>
            <Layer {...routeLayerStyle} />
          </Source>
        )}
      </Map>

      {/* Control Panel */}
      <div className="absolute top-4 left-4 bg-gray-900 border border-gray-700 rounded-xl p-4 w-72 space-y-3 shadow-lg">
        <p className="text-sm font-medium text-white">Crime-Aware Route Planner</p>

        <div className="space-y-1 text-xs text-gray-400">
          <p>
            <span className="inline-block w-2 h-2 rounded-full bg-green-500 mr-2" />
            {origin ? `Origin: ${origin.lat.toFixed(4)}, ${origin.lng.toFixed(4)}` : "Click map to set origin"}
          </p>
          <p>
            <span className="inline-block w-2 h-2 rounded-full bg-red-500 mr-2" />
            {destination ? `Destination: ${destination.lat.toFixed(4)}, ${destination.lng.toFixed(4)}` : "Click map to set destination"}
          </p>
        </div>

        <p className="text-xs text-gray-500">
          Next click sets: <span className="text-white">{selectingFor}</span>
        </p>

        {error && <p className="text-xs text-red-400">{error}</p>}

        {route && (
          <p className="text-xs text-green-400">
            Route found — crime score: {route.safety_info.total_crime_score}
          </p>
        )}

        <div className="flex gap-2">
          <button
            onClick={getRoute}
            disabled={!origin || !destination || loading}
            className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white text-xs py-2 rounded-lg transition-colors"
          >
            {loading ? "Routing..." : "Get Route"}
          </button>
          <button
            onClick={clearAll}
            className="px-3 py-2 bg-gray-700 hover:bg-gray-600 text-white text-xs rounded-lg transition-colors"
          >
            Clear
          </button>
        </div>
      </div>
    </div>
  );
}