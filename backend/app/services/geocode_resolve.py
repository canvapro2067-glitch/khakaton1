"""Точные координаты: Яндекс.Геокодер → OSM Nominatim → локальная улица (fallback)."""
from __future__ import annotations

import asyncio
import time

import httpx

from .geo import geocode_address
from .yandex import geocode as yandex_geocode

_nominatim_lock = asyncio.Lock()
_last_nominatim = 0.0


async def nominatim_geocode(address: str) -> tuple[float, float] | None:
    q = (address or "").strip()
    if not q:
        return None
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": f"{q}, Гродно, Беларусь",
        "format": "json",
        "limit": 1,
        "countrycodes": "by",
    }
    headers = {"User-Agent": "moloko-mir-grodno-logistics/1.0 (hackathon demo)"}
    global _last_nominatim
    try:
        async with _nominatim_lock:
            wait = 1.15 - (time.monotonic() - _last_nominatim)
            if wait > 0:
                await asyncio.sleep(wait)
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(url, params=params, headers=headers)
            _last_nominatim = time.monotonic()
        if r.status_code != 200:
            return None
        items = r.json()
        if not items:
            return None
        lat = float(items[0]["lat"])
        lon = float(items[0]["lon"])
        return lat, lon
    except Exception:
        return None


async def resolve_address_coords(address: str) -> tuple[float, float, str]:
    addr = (address or "").strip()
    if not addr:
        lat, lon, src = geocode_address(addr)
        return lat, lon, src

    yx = await yandex_geocode(addr)
    if yx:
        return yx[0], yx[1], "yandex"

    osm = await nominatim_geocode(addr)
    if osm:
        return osm[0], osm[1], "osm"

    lat, lon, src = geocode_address(addr)
    return lat, lon, src


async def resolve_many(addresses: list[str], concurrency: int = 4) -> list[tuple[float, float, str]]:
    sem = asyncio.Semaphore(concurrency)

    async def one(addr: str) -> tuple[float, float, str]:
        async with sem:
            return await resolve_address_coords(addr)

    return await asyncio.gather(*(one(a) for a in addresses))


async def apply_geocode_to_orders(orders: list, *, db) -> dict:
    """Обновить lat/lon у списка Order (уже загруженных из БД)."""
    if not orders:
        return {"updated": 0, "yandex": 0, "osm": 0, "approx": 0}
    coords = await resolve_many([o.address for o in orders])
    stats = {"yandex": 0, "osm": 0, "approx": 0}
    for o, (lat, lon, src) in zip(orders, coords):
        o.lat = lat
        o.lon = lon
        o.geo_source = src
        if src == "yandex":
            stats["yandex"] += 1
        elif src == "osm":
            stats["osm"] += 1
        else:
            stats["approx"] += 1
        warn_parts = [p for p in (o.warning or "").split("; ") if p and "Координаты" not in p]
        if src not in ("yandex", "osm"):
            warn_parts.append("Координаты приблизительные, рекомендуется проверить")
        o.warning = "; ".join(warn_parts)
    db.commit()
    return {"updated": len(orders), **stats}