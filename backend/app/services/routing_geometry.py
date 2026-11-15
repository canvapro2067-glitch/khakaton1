"""Геометрия рейса по дорогам: Яндекс Routing (если ключ валиден) или OSRM."""
from __future__ import annotations

import asyncio

import httpx

from ..config import YANDEX_MAPS_API_KEY, YANDEX_ROUTING_API_KEY
from .yandex import route_geometry as yandex_route_geometry

OSRM = "https://router.project-osrm.org/route/v1/driving"


def _looks_like_roads(line: list[list[float]], waypoints: int) -> bool:
    if len(line) < 2:
        return False
    return len(line) >= max(waypoints + 4, waypoints * 3)


async def osrm_geometry(points: list[tuple[float, float]]) -> list[list[float]]:
    if len(points) < 2:
        return [[p[0], p[1]] for p in points]
    coords = ";".join(f"{lon},{lat}" for lat, lon in points)
    try:
        async with httpx.AsyncClient(timeout=45) as client:
            r = await client.get(
                f"{OSRM}/{coords}",
                params={"overview": "full", "geometries": "geojson", "steps": "false"},
            )
            if r.status_code != 200:
                return [[p[0], p[1]] for p in points]
            routes = r.json().get("routes") or []
            if not routes:
                return [[p[0], p[1]] for p in points]
            raw = routes[0].get("geometry", {}).get("coordinates") or []
            return [[float(c[1]), float(c[0])] for c in raw if len(c) >= 2]
    except Exception:
        return [[p[0], p[1]] for p in points]


async def road_polyline(points: list[tuple[float, float]]) -> list[list[float]]:
    if len(points) < 2:
        return [[p[0], p[1]] for p in points]
    if YANDEX_ROUTING_API_KEY or YANDEX_MAPS_API_KEY:
        yx = await yandex_route_geometry(points)
        if _looks_like_roads(yx, len(points)):
            return yx
    return await osrm_geometry(points)


def road_polyline_sync(points: list[tuple[float, float]]) -> list[list[float]]:
    return asyncio.run(road_polyline(points))