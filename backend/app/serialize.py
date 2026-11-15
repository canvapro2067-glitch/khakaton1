import json

from .models import Order, RoadRestriction, Route, RouteStop, Unassigned, User, Vehicle
from .services.costs import route_distance_m
from .services.geo import DEPOT


def vehicle_dict(v: Vehicle, extra: dict | None = None) -> dict:
    d = {
        "id": v.id,
        "brand": v.brand,
        "model": v.model,
        "plate": v.plate,
        "capacity_kg": v.capacity_kg,
        "max_mass_kg": v.max_mass_kg,
        "height_m": v.height_m,
        "width_m": v.width_m,
        "length_m": v.length_m,
        "is_active": v.is_active,
        "color": v.color,
        "note": v.note,
        "title": f"{v.brand} {v.model}",
    }
    if extra:
        d.update(extra)
    return d


def order_dict(o: Order, extra: dict | None = None) -> dict:
    d = {
        "id": o.id,
        "name": o.name,
        "address": o.address,
        "weight_kg": o.weight_kg,
        "preferred_time": o.preferred_time,
        "window_start": o.window_start,
        "window_end": o.window_end,
        "unload_min": o.unload_min,
        "lat": o.lat,
        "lon": o.lon,
        "geo_source": o.geo_source,
        "is_duplicate": o.is_duplicate,
        "warning": o.warning,
        "restricted_historic": o.restricted_historic,
        "contact_phone": getattr(o, "contact_phone", "") or "",
        "dispatcher_note": getattr(o, "dispatcher_note", "") or "",
    }
    if extra:
        d.update(extra)
    return d


def user_dict(u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "full_name": u.full_name,
        "phone": u.phone or "",
        "role": u.role,
        "vehicle_id": u.vehicle_id,
        "is_active": bool(u.is_active),
        "created_at": u.created_at.isoformat() if getattr(u, "created_at", None) else None,
        "last_lat": getattr(u, "last_lat", None),
        "last_lon": getattr(u, "last_lon", None),
        "last_geo_at": u.last_geo_at.isoformat() if getattr(u, "last_geo_at", None) else None,
        "geo_enabled": bool(getattr(u, "geo_enabled", True)),
        "shift_status": getattr(u, "shift_status", None) or "waiting",
        "shift_started_at": u.shift_started_at.isoformat() if getattr(u, "shift_started_at", None) else None,
        "shift_ended_at": u.shift_ended_at.isoformat() if getattr(u, "shift_ended_at", None) else None,
    }


def stop_dict(s: RouteStop) -> dict:
    o = s.order
    unload_s = None
    if s.started_at and s.completed_at:
        unload_s = max(0, int((s.completed_at - s.started_at).total_seconds()))
    return {
        "id": s.id,
        "seq": s.seq,
        "status": s.status,
        "eta": s.eta,
        "distance_from_prev_m": s.distance_from_prev_m,
        "travel_s": s.travel_s,
        "problem_reason": getattr(s, "problem_reason", "") or "",
        "problem_text": s.problem_text,
        "dispatcher_reply": getattr(s, "dispatcher_reply", "") or "",
        "arrived_at": s.started_at.isoformat() if s.started_at else None,
        "unloaded_at": s.completed_at.isoformat() if s.completed_at else None,
        "unloading_started_at": s.unloading_started_at.isoformat() if getattr(s, "unloading_started_at", None) else None,
        "started_at": s.started_at.isoformat() if s.started_at else None,
        "completed_at": s.completed_at.isoformat() if s.completed_at else None,
        "actual_weight_kg": getattr(s, "actual_weight_kg", None),
        "driver_comment": getattr(s, "driver_comment", "") or "",
        "event_lat": getattr(s, "event_lat", None),
        "event_lon": getattr(s, "event_lon", None),
        "unload_duration_s": unload_s,
        "order": order_dict(o) if o else None,
    }


def route_dict(r: Route, with_stops=True) -> dict:
    d = {
        "id": r.id,
        "vehicle": vehicle_dict(r.vehicle) if r.vehicle else None,
        "status": r.status,
        "load_kg": r.load_kg,
        "distance_m": route_distance_m(r),
        "distance_plan_m": r.distance_m,
        "duration_s": r.duration_s,
        "finish_time": r.finish_time,
        "warning": r.warning,
        "stops_count": len(r.stops),
        "fill": (r.load_kg / r.vehicle.capacity_kg) if r.vehicle and r.vehicle.capacity_kg else 0,
    }
    if with_stops:
        d["stops"] = [stop_dict(s) for s in r.stops]
    geometry: list = []
    if r.geometry_json:
        try:
            geometry = json.loads(r.geometry_json)
        except json.JSONDecodeError:
            geometry = []
    d["geometry"] = geometry
    return d


def restriction_dict(r: RoadRestriction) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "street_pattern": r.street_pattern,
        "max_capacity_kg": r.max_capacity_kg,
        "max_mass_kg": r.max_mass_kg,
        "max_height_m": r.max_height_m,
        "max_width_m": r.max_width_m,
        "max_length_m": r.max_length_m,
        "vehicle_id": r.vehicle_id,
        "note": r.note,
        "is_active": r.is_active,
    }


def unassigned_dict(u: Unassigned) -> dict:
    return {
        "id": u.id,
        "order_id": u.order_id,
        "reason": u.reason,
        "conflicts": u.conflicts,
        "suggestions": u.suggestions,
        "order": order_dict(u.order) if getattr(u, "order", None) else None,
    }


def depot_dict(settings: dict) -> dict:
    return {
        "name": settings.get("depot_name", DEPOT["name"]),
        "address": settings.get("depot_address", DEPOT["address"]),
        "lat": float(settings.get("depot_lat", DEPOT["lat"])),
        "lon": float(settings.get("depot_lon", DEPOT["lon"])),
    }
