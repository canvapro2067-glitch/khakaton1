"""Координаты дома: локальный кэш Nominatim → HTTP Яндекс (если ключ) → Nominatim → улица."""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import httpx

from .address_format import geocode_queries, pretty_grodno_address
from .geo import geocode_address, in_grodno
from .yandex import geocode as yandex_geocode

CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "grodno_geocode.json"
HOUSE_KINDS = {"building", "house", "apartments", "shop", "amenity", "office", "retail", "yes"}

_file_cache: dict[str, dict] | None = None
_nominatim_lock = asyncio.Lock()
_last_nominatim = 0.0


def _load_file_cache() -> dict[str, dict]:
    global _file_cache
    if _file_cache is not None:
        return _file_cache
    if CACHE_PATH.exists():
        try:
            _file_cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            _file_cache = {}
    else:
        _file_cache = {}
    return _file_cache


def _from_cache(address: str) -> tuple[float, float, str] | None:
    cache = _load_file_cache()
    rec = cache.get(address) or cache.get(address.strip())
    if not rec:
        low = address.strip().lower()
        for k, v in cache.items():
            if k.lower() == low:
                rec = v
                break
    if not rec or rec.get("lat") is None:
        return None
    lat, lon = float(rec["lat"]), float(rec["lon"])
    if not in_grodno(lat, lon):
        return None
    kind = rec.get("kind") or ""
    src = "osm" if kind in HOUSE_KINDS or rec.get("src") == "osm" else "osm-street"
    if kind in HOUSE_KINDS:
        src = "osm"
    return lat, lon, src


def normalize_grodno_ll(lat: float, lon: float) -> tuple[float, float] | None:
    if in_grodno(lat, lon):
        return lat, lon
    if in_grodno(lon, lat):
        return lon, lat
    return None


async def nominatim_geocode(address: str) -> tuple[float, float, str] | None:
    global _last_nominatim
    headers = {"User-Agent": "moloko-mir-grodno-logistics/1.0 (hackathon demo)"}
    best: tuple[float, float, str] | None = None
    async with _nominatim_lock:
        async with httpx.AsyncClient(timeout=18) as client:
            for q in geocode_queries(address):
                wait = 1.1 - (time.monotonic() - _last_nominatim)
                if wait > 0:
                    await asyncio.sleep(wait)
                try:
                    r = await client.get(
                        "https://nominatim.openstreetmap.org/search",
                        params={
                            "q": q,
                            "format": "json",
                            "limit": 1,
                            "countrycodes": "by",
                            "addressdetails": 1,
                        },
                        headers=headers,
                    )
                except Exception:
                    _last_nominatim = time.monotonic()
                    continue
                _last_nominatim = time.monotonic()
                if r.status_code != 200:
                    continue
                items = r.json() or []
                if not items:
                    continue
                item = items[0]
                pt = normalize_grodno_ll(float(item["lat"]), float(item["lon"]))
                if not pt:
                    continue
                kind = item.get("addresstype") or item.get("type") or ""
                src = "osm" if (kind in HOUSE_KINDS or item.get("class") in {"building", "shop", "amenity"}) else "osm-street"
                if src == "osm":
                    return pt[0], pt[1], src
                if best is None:
                    best = (pt[0], pt[1], src)
    return best


async def resolve_address_coords(address: str, *, live: bool = False) -> tuple[float, float, str]:
    addr = (address or "").strip()
    if not addr:
        lat, lon, src = geocode_address(addr)
        return lat, lon, src

    cached = _from_cache(addr)
    if cached:
        return cached

    if live:
        yx = await yandex_geocode(pretty_grodno_address(addr))
        if yx:
            pt = normalize_grodno_ll(yx[0], yx[1])
            if pt:
                return pt[0], pt[1], "yandex"
        osm = await nominatim_geocode(addr)
        if osm:
            return osm

    lat, lon, src = geocode_address(addr)
    return lat, lon, src


async def resolve_many(addresses: list[str], concurrency: int = 1) -> list[tuple[float, float, str]]:
    cache: dict[str, tuple[float, float, str]] = {}
    out: list[tuple[float, float, str]] = []
    for addr in addresses:
        key = (addr or "").strip().lower()
        if key not in cache:
            cache[key] = await resolve_address_coords(addr)
        out.append(cache[key])
    return out


async def apply_geocode_to_orders(orders: list, *, db) -> dict:
    if not orders:
        return {"updated": 0, "yandex": 0, "osm": 0, "approx": 0}
    coords = await resolve_many([o.address for o in orders])
    stats = {"yandex": 0, "osm": 0, "approx": 0, "updated": 0}
    for o, (lat, lon, src) in zip(orders, coords):
        o.lat = lat
        o.lon = lon
        o.geo_source = src
        if src == "yandex":
            stats["yandex"] += 1
        elif src.startswith("osm"):
            stats["osm"] += 1
        else:
            stats["approx"] += 1
        stats["updated"] += 1
        warn_parts = [p for p in (o.warning or "").split("; ") if p and "Координаты" not in p]
        if src not in ("yandex", "osm"):
            warn_parts.append("Координаты приблизительные, рекомендуется проверить")
        o.warning = "; ".join(warn_parts)
    db.commit()
    return stats
