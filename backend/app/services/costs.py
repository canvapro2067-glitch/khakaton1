"""Ориентировочные затраты плана: только топливо по пробегу (без ФОТ водителей)."""
from __future__ import annotations

import json

from ..models import Route, Vehicle
from .geo import haversine_m


def polyline_length_m(line: list[list[float]]) -> int:
    if not line or len(line) < 2:
        return 0
    total = 0
    for a, b in zip(line, line[1:]):
        total += haversine_m((float(a[0]), float(a[1])), (float(b[0]), float(b[1])))
    return int(total)


def route_distance_m(route: Route) -> int:
    """Пробег для расчёта топлива: по дорожной геометрии, если есть, иначе из солвера."""
    if route.geometry_json:
        try:
            geom = json.loads(route.geometry_json)
            if isinstance(geom, list):
                road_m = polyline_length_m(geom)
                if road_m > 0:
                    return road_m
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return int(route.distance_m or 0)


def _float_setting(settings: dict, key: str, default: float) -> float:
    raw = settings.get(key)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _fuel_byn(km: float, fuel_l_per_100km: float, fuel_price_byn: float) -> tuple[float, float]:
    liters = km * fuel_l_per_100km / 100.0
    return liters, liters * fuel_price_byn


def fleet_costs(routes: list[Route], vehicles: dict[int, Vehicle], settings: dict) -> dict:
    fuel_l = _float_setting(settings, "fuel_l_per_100km", 18.0)
    fuel_price = _float_setting(settings, "fuel_price_byn", 2.89)

    plan_km = sum(int(r.distance_m or 0) for r in routes) / 1000.0
    road_km = sum(route_distance_m(r) for r in routes) / 1000.0
    fleet_km = road_km if road_km > 0 else plan_km

    fleet_liters, fuel_cost = _fuel_byn(fleet_km, fuel_l, fuel_price)
    driver_hours = sum(int(r.duration_s or 0) for r in routes) / 3600.0

    per_vehicle: list[dict] = []
    for r in routes:
        km = route_distance_m(r) / 1000.0
        hours = (r.duration_s or 0) / 3600.0
        liters, cost = _fuel_byn(km, fuel_l, fuel_price)
        v = vehicles.get(r.vehicle_id)
        cap = v.capacity_kg if v else 0
        per_vehicle.append(
            {
                "route_id": r.id,
                "plate": v.plate if v else "",
                "km": round(km, 1),
                "hours": round(hours, 2),
                "fuel_l": round(liters, 1),
                "load_kg": r.load_kg,
                "capacity": cap,
                "cost": round(cost, 2),
            }
        )

    return {
        "fleet_km": round(fleet_km, 1),
        "fleet_km_plan": round(plan_km, 1),
        "fleet_km_roads": round(road_km, 1) if road_km > 0 else None,
        "driver_hours": round(driver_hours, 2),
        "fuel_l": round(fleet_liters, 1),
        "fuel_price_byn": fuel_price,
        "fuel_l_per_100km": fuel_l,
        "fuel_cost_byn": round(fuel_cost, 2),
        "cost_byn": round(fuel_cost, 2),
        "cost_basis": "fuel_only",
        "per_vehicle": per_vehicle,
    }