"""Yandex Routing API: матрица и геометрия. Без ключа — пустой ответ, солвер использует свою матрицу."""
from __future__ import annotations

import json

import httpx

from ..config import YANDEX_MAPS_API_KEY, YANDEX_ROUTING_API_KEY
from .geo import DEPOT


def maps_key() -> str:
    return YANDEX_MAPS_API_KEY


async def geocode(address: str) -> tuple[float, float] | None:
    key = YANDEX_MAPS_API_KEY
    addr = (address or "").strip()
    if not key or not addr:
        return None
    url = "https://geocode-maps.yandex.ru/1.x/"
    queries = [
        f"Беларусь, Гродно, {addr}",
        f"Гродно, {addr}",
        addr,
    ]
    seen: set[str] = set()
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            for q in queries:
                if q in seen:
                    continue
                seen.add(q)
                r = await client.get(url, params={"apikey": key, "geocode": q, "format": "json", "results": 1})
                if r.status_code != 200:
                    continue
                members = r.json().get("response", {}).get("GeoObjectCollection", {}).get("featureMember") or []
                if not members:
                    continue
                pos = members[0].get("GeoObject", {}).get("Point", {}).get("pos")
                if not pos:
                    continue
                lon, lat = map(float, str(pos).split())
                return lat, lon
    except Exception:
        return None
    return None


def _chunks(items, n=49):
    for i in range(0, len(items), n):
        yield items[i : i + n]


async def route_geometry(points: list[tuple[float, float]]) -> list[list[float]]:
    """Ломаная маршрута. API лимит ~50 точек — режем на сегменты."""
    key = YANDEX_ROUTING_API_KEY or YANDEX_MAPS_API_KEY
    if not key or len(points) < 2:
        return [[p[0], p[1]] for p in points]
    line: list[list[float]] = []
    seq = [DEPOT["lat"], DEPOT["lon"]] if False else None
    del seq
    pts = points[:]
    for part in _chunks(pts, 49):
        if line and part[0] != pts[0]:
            part = [pts[max(0, pts.index(part[0]) - 1)]] + part if part[0] in pts else part
        wp = "|".join(f"{p[1]},{p[0]}" for p in part)
        url = "https://api.routing.yandex.net/v2/route"
        params = {"apikey": key, "waypoints": wp, "mode": "truck", "traffic": "future"}
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.get(url, params=params)
                if r.status_code != 200:
                    line.extend([[p[0], p[1]] for p in part])
                    continue
                data = r.json()
                legs = data.get("route", {}).get("legs") or []
                if not legs:
                    line.extend([[p[0], p[1]] for p in part])
                    continue
                for leg in legs:
                    for step in leg.get("steps", []):
                        polyline = step.get("polyline", {}).get("points") or []
                        for pt in polyline:
                            if isinstance(pt, dict):
                                line.append([pt.get("latitude") or pt.get("lat"), pt.get("longitude") or pt.get("lon")])
        except Exception:
            line.extend([[p[0], p[1]] for p in part])
    return line or [[p[0], p[1]] for p in points]
