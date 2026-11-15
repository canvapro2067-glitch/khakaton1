"""Точные координаты: Яндекс.Геокодер (дом) → улица в Гродно. OSM не используем — часто путает дома."""
from __future__ import annotations

import asyncio

from .geo import geocode_address, haversine_m, in_grodno, street_centroid
from .yandex import geocode as yandex_geocode

_MAX_FROM_STREET_M = 2500


def _accept(lat: float, lon: float, address: str) -> bool:
    if not in_grodno(lat, lon):
        return False
    hint = street_centroid(address)
    if hint and haversine_m((lat, lon), hint) > _MAX_FROM_STREET_M:
        return False
    return True


async def resolve_address_coords(address: str) -> tuple[float, float, str]:
    addr = (address or "").strip()
    if not addr:
        lat, lon, src = geocode_address(addr)
        return lat, lon, src

    yx = await yandex_geocode(addr)
    if yx and _accept(yx[0], yx[1], addr):
        return yx[0], yx[1], "yandex"

    lat, lon, src = geocode_address(addr)
    return lat, lon, src


async def resolve_many(addresses: list[str], concurrency: int = 4) -> list[tuple[float, float, str]]:
    sem = asyncio.Semaphore(concurrency)
    cache: dict[str, tuple[float, float, str]] = {}

    async def one(addr: str) -> tuple[float, float, str]:
        key = (addr or "").strip().lower()
        if key in cache:
            return cache[key]
        async with sem:
            if key in cache:
                return cache[key]
            val = await resolve_address_coords(addr)
            cache[key] = val
            return val

    return await asyncio.gather(*(one(a) for a in addresses))


async def apply_geocode_to_orders(orders: list, *, db) -> dict:
    """Обновить lat/lon у списка Order. Пишем только результат Яндекса, OSM не трогаем."""
    if not orders:
        return {"updated": 0, "yandex": 0, "osm": 0, "approx": 0}
    coords = await resolve_many([o.address for o in orders])
    stats = {"yandex": 0, "osm": 0, "approx": 0, "updated": 0}
    for o, (lat, lon, src) in zip(orders, coords):
        if src != "yandex":
            stats["approx"] += 1
            continue
        o.lat = lat
        o.lon = lon
        o.geo_source = src
        stats["yandex"] += 1
        stats["updated"] += 1
        warn_parts = [p for p in (o.warning or "").split("; ") if p and "Координаты" not in p]
        o.warning = "; ".join(warn_parts)
    db.commit()
    return stats
