import asyncio
import json
import os
import math
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from .async_util import run_coro_sync
from .auth import create_token, get_current_user, hash_password, require_dispatcher, require_driver, verify_password
from .config import EXCEL_PATH, YANDEX_MAPS_API_KEY, route_geometry_enabled
from .database import get_db
from .models import (
    DriverMessage,
    DriverNotification,
    Order,
    RoadRestriction,
    Route,
    RouteStop,
    Setting,
    TripArchive,
    Unassigned,
    User,
    Vehicle,
)
from .seed import seed_if_empty
from .serialize import depot_dict, order_dict, restriction_dict, route_dict, stop_dict, user_dict, vehicle_dict
from .services.costs import fleet_costs
from .services.excel_import import import_workbook, preview_workbook
from .services.geo import DEPOT, in_grodno
from .services.geocode_resolve import apply_geocode_to_orders, resolve_address_coords
from .services.restrictions import historic_forbidden_geometry, vehicle_allowed
from .services.routing_geometry import road_polyline
from .services.vrp import SolveOrder, SolveVehicle, solve
from .services.yandex import maps_key

router = APIRouter()


class LoginIn(BaseModel):
    username: str
    password: str


class VehicleIn(BaseModel):
    brand: str
    model: str
    plate: str
    capacity_kg: int
    max_mass_kg: int = 0
    height_m: float = 2.5
    width_m: float = 2.2
    length_m: float = 6.0
    is_active: bool = True
    color: str = "#0F6B8F"
    note: str = ""


class OrderPatch(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    weight_kg: Optional[int] = None
    preferred_time: Optional[str] = None
    window_start: Optional[str] = None
    window_end: Optional[str] = None
    unload_min: Optional[int] = None
    lat: Optional[float] = None
    lon: Optional[float] = None


class RestrictionIn(BaseModel):
    name: str
    street_pattern: str
    max_capacity_kg: Optional[int] = None
    max_mass_kg: Optional[int] = None
    max_height_m: Optional[float] = None
    max_width_m: Optional[float] = None
    max_length_m: Optional[float] = None
    vehicle_id: Optional[int] = None
    note: str = ""
    is_active: bool = True


class ReassignIn(BaseModel):
    order_id: int
    vehicle_id: int


class ProblemIn(BaseModel):
    text: str = ""
    reason: str = ""
    comment: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None
    at: Optional[str] = None


class DriverCreateIn(BaseModel):
    full_name: str
    username: str
    phone: str = ""
    password: str
    vehicle_id: Optional[int] = None


class DriverPatchIn(BaseModel):
    full_name: Optional[str] = None
    username: Optional[str] = None
    phone: Optional[str] = None
    vehicle_id: Optional[int] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class DriverStartIn(BaseModel):
    arrive: bool = False
    lat: Optional[float] = None
    lon: Optional[float] = None
    at: Optional[str] = None


class GeoIn(BaseModel):
    lat: Optional[float] = None
    lon: Optional[float] = None
    enabled: Optional[bool] = None


class OrderCoordIn(BaseModel):
    id: int
    lat: float
    lon: float
    source: str = "yandex"


class OrderCoordsIn(BaseModel):
    items: list[OrderCoordIn]


class StopEventIn(BaseModel):
    lat: Optional[float] = None
    lon: Optional[float] = None
    at: Optional[str] = None
    comment: Optional[str] = None
    actual_weight_kg: Optional[int] = None
    client_id: Optional[str] = None


class ChatIn(BaseModel):
    text: str
    stop_id: Optional[int] = None


class ShiftIn(BaseModel):
    status: str
    comment: Optional[str] = None


class ProblemReplyIn(BaseModel):
    reply: str


def settings_map(db: Session) -> dict:
    return {s.key: s.value for s in db.query(Setting).all()}


def _norm_phone(raw: str | None) -> str:
    return "".join(ch for ch in (raw or "") if ch.isdigit() or ch == "+")


def _find_user_by_login(db: Session, login: str) -> User | None:
    q = (login or "").strip()
    if not q:
        return None
    user = db.query(User).filter(User.username == q).first()
    if user:
        return user
    user = db.query(User).filter(User.phone == q).first()
    if user:
        return user
    digits = "".join(ch for ch in q if ch.isdigit())
    if len(digits) >= 9:
        for u in db.query(User).filter(User.phone != "").all():
            if "".join(ch for ch in u.phone if ch.isdigit())[-9:] == digits[-9:]:
                return u
    return None


def _assert_vehicle_free(db: Session, vehicle_id: int | None, except_user_id: int | None = None) -> None:
    if not vehicle_id:
        return
    st = settings_map(db)
    if str(st.get("allow_shared_vehicle", "0")) == "1":
        return
    q = db.query(User).filter(
        User.role == "driver",
        User.is_active.is_(True),
        User.vehicle_id == vehicle_id,
    )
    if except_user_id:
        q = q.filter(User.id != except_user_id)
    other = q.first()
    if other:
        raise HTTPException(400, f"Автомобиль уже закреплён за {other.full_name or other.username}")


def _current_stop(stops: list[RouteStop]) -> RouteStop | None:
    for s in sorted(stops, key=lambda x: x.seq):
        if s.status not in ("done", "problem"):
            return s
    return None


def _driver_live(db: Session, u: User) -> dict:
    vehicle = db.get(Vehicle, u.vehicle_id) if u.vehicle_id else None
    routes = []
    if u.vehicle_id:
        routes = (
            db.query(Route)
            .options(joinedload(Route.stops).joinedload(RouteStop.order), joinedload(Route.vehicle))
            .filter(Route.vehicle_id == u.vehicle_id)
            .order_by(Route.id)
            .all()
        )
    stops = [s for r in routes for s in r.stops]
    current = _current_stop(stops)
    done_n = sum(1 for s in stops if s.status == "done")
    problem_n = sum(1 for s in stops if s.status == "problem")
    remaining = sum(1 for s in stops if s.status not in ("done", "problem"))
    on_route = any(s.status in ("enroute", "at_stop") for s in stops)
    load_kg = sum(r.load_kg for r in routes)
    return {
        **user_dict(u),
        "vehicle": vehicle_dict(vehicle) if vehicle else None,
        "route_status": "on_route" if on_route else ("planned" if remaining else ("done" if stops else "idle")),
        "stops_total": len(stops),
        "stops_done": done_n,
        "stops_left": remaining,
        "stops_problem": problem_n,
        "load_kg": load_kg,
        "current_stop": (
            {
                "id": current.id,
                "seq": current.seq,
                "status": current.status,
                "eta": current.eta,
                "name": current.order.name if current.order else "",
                "address": current.order.address if current.order else "",
                "arrived_at": current.started_at.isoformat() if current.started_at else None,
                "completed_at": current.completed_at.isoformat() if current.completed_at else None,
            }
            if current
            else None
        ),
        "routes": [route_dict(r, with_stops=False) for r in routes],
        "last_lat": getattr(u, "last_lat", None),
        "last_lon": getattr(u, "last_lon", None),
        "last_geo_at": u.last_geo_at.isoformat() if getattr(u, "last_geo_at", None) else None,
        "shift_status": getattr(u, "shift_status", None) or "waiting",
        "geo_enabled": bool(getattr(u, "geo_enabled", True)),
    }


def depot_tuple(st: dict) -> tuple[float, float]:
    return float(st.get("depot_lat", DEPOT["lat"])), float(st.get("depot_lon", DEPOT["lon"]))


def route_waypoints(route: Route, depot: tuple[float, float]) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = [depot]
    for s in sorted(route.stops, key=lambda x: x.seq):
        if s.order and s.order.lat is not None and s.order.lon is not None:
            pts.append((float(s.order.lat), float(s.order.lon)))
    pts.append(depot)
    return pts


async def fill_route_geometries(db: Session) -> None:
    st = settings_map(db)
    depot = depot_tuple(st)
    routes = db.query(Route).options(joinedload(Route.stops).joinedload(RouteStop.order)).all()
    sem = asyncio.Semaphore(5)

    async def build(route: Route) -> None:
        async with sem:
            pts = route_waypoints(route, depot)
            line = await road_polyline(pts) if len(pts) >= 2 else []
            route.geometry_json = json.dumps(line, ensure_ascii=False)

    await asyncio.gather(*(build(r) for r in routes))
    db.commit()


def _parse_client_at(raw: str | None) -> datetime:
    if not raw:
        return datetime.utcnow()
    try:
        s = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo:
            dt = dt.replace(tzinfo=None)
        return dt
    except ValueError:
        return datetime.utcnow()


def _notify(db: Session, user_id: int, key: str, title: str, body: str, kind: str = "info") -> None:
    if key and db.query(DriverNotification).filter(DriverNotification.user_id == user_id, DriverNotification.key == key).first():
        return
    db.add(DriverNotification(user_id=user_id, key=key, title=title, body=body, kind=kind))


def _notify_dispatchers(db: Session, key: str, title: str, body: str, kind: str = "info") -> None:
    for u in db.query(User).filter(User.role == "dispatcher", User.is_active.is_(True)).all():
        _notify(db, u.id, f"{key}:d{u.id}", title, body, kind)


def _archive_current_routes(db: Session) -> None:
    routes = db.query(Route).options(joinedload(Route.stops).joinedload(RouteStop.order), joinedload(Route.vehicle)).all()
    if not routes:
        return
    drivers = {u.vehicle_id: u for u in db.query(User).filter(User.role == "driver", User.vehicle_id.isnot(None)).all()}
    today = datetime.utcnow().strftime("%Y-%m-%d")
    for r in routes:
        stops = r.stops or []
        if not stops:
            continue
        drv = drivers.get(r.vehicle_id)
        db.add(
            TripArchive(
                vehicle_id=r.vehicle_id,
                driver_id=drv.id if drv else None,
                plate=r.vehicle.plate if r.vehicle else "",
                route_date=today,
                orders_n=len(stops),
                done_n=sum(1 for s in stops if s.status == "done"),
                problem_n=sum(1 for s in stops if s.status == "problem"),
                weight_kg=r.load_kg,
                distance_m=r.distance_m,
                started_at=today,
                finished_at=r.finish_time or "",
                detail_json=json.dumps(
                    {
                        "stops": [
                            {
                                "name": s.order.name if s.order else "",
                                "status": s.status,
                                "eta": s.eta,
                            }
                            for s in stops
                        ]
                    },
                    ensure_ascii=False,
                ),
            )
        )
    db.commit()


def _refresh_shift(user: User, stops: list[RouteStop]) -> str:
    if user.shift_status in ("break", "returning", "finished"):
        if user.shift_status == "finished":
            return user.shift_status
        if user.shift_status == "break":
            return user.shift_status
        if user.shift_status == "returning" and all(s.status in ("done", "problem") for s in stops):
            return "returning"
    if any(s.status == "unloading" for s in stops):
        user.shift_status = "unloading"
    elif any(s.status == "at_stop" for s in stops):
        user.shift_status = "at_stop"
    elif any(s.status == "enroute" for s in stops):
        user.shift_status = "on_route"
    elif stops and all(s.status in ("done", "problem") for s in stops):
        user.shift_status = "returning" if user.shift_status != "finished" else "finished"
    elif user.shift_status in ("ready", "on_route"):
        pass
    elif stops:
        user.shift_status = user.shift_status or "waiting"
    return user.shift_status


def persist_solution(db: Session, result) -> None:
    _archive_current_routes(db)
    for u in db.query(User).filter(User.role == "driver").all():
        _notify(db, u.id, f"route:{int(datetime.utcnow().timestamp())}:{u.id}", "Назначен новый маршрут", "Диспетчер пересчитал доставки. Откройте кабинет.", "route")
    db.query(DriverMessage).update({DriverMessage.stop_id: None})
    db.query(RouteStop).delete()
    db.query(Route).delete()
    db.query(Unassigned).delete()
    db.commit()
    vehicles = {v.id: v for v in db.query(Vehicle).all()}
    for r in result.routes:
        route = Route(
            vehicle_id=r.vehicle_id,
            status="planned",
            load_kg=r.load,
            distance_m=r.distance_m,
            duration_s=r.duration_s,
            finish_time=r.finish,
            warning=r.warning,
        )
        db.add(route)
        db.flush()
        for s in r.stops:
            db.add(
                RouteStop(
                    route_id=route.id,
                    order_id=s.order_id,
                    seq=s.seq,
                    eta=s.eta,
                    distance_from_prev_m=s.dist_m,
                    travel_s=s.travel_s,
                    status="pending",
                )
            )
        _ = vehicles
    for u in result.unassigned:
        db.add(Unassigned(order_id=u.order_id, reason=u.reason, conflicts=u.conflicts, suggestions=u.suggestions))
    db.commit()


def run_solver(db: Session, *, fill_geometry: bool = True):
    orders = db.query(Order).all()
    vehicles = db.query(Vehicle).all()
    restrictions = db.query(RoadRestriction).all()
    st = settings_map(db)
    so = [
        SolveOrder(
            id=o.id,
            name=o.name,
            address=o.address,
            weight=o.weight_kg,
            lat=o.lat or DEPOT["lat"],
            lon=o.lon or DEPOT["lon"],
            preferred=o.preferred_time,
            window_start=o.window_start,
            window_end=o.window_end,
            unload_min=o.unload_min,
            historic=o.restricted_historic,
        )
        for o in orders
    ]
    sv = [SolveVehicle(id=v.id, plate=v.plate, capacity=v.capacity_kg, raw=v) for v in vehicles]
    result = solve(so, sv, restrictions, st, depot=depot_tuple(st))
    persist_solution(db, result)
    if fill_geometry and route_geometry_enabled():
        run_coro_sync(fill_route_geometries(db))
    return result


@router.post("/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    seed_if_empty(db)
    user = _find_user_by_login(db, body.username)
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Неверный логин или пароль")
    if not user.is_active:
        raise HTTPException(403, "Аккаунт заблокирован. Обратитесь к диспетчеру")
    return {"token": create_token(user), "user": user_dict(user)}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_dict(user)


@router.get("/config")
def public_config(db: Session = Depends(get_db)):
    st = settings_map(db)
    return {
        "yandex_maps_key": maps_key() or YANDEX_MAPS_API_KEY,
        "depot": depot_dict(st),
        "company": st.get("company", "ОАО «Молочный мир»"),
        "dispatcher_name": st.get("dispatcher_name", "Диспетчер логистики"),
        "dispatcher_phone": st.get("dispatcher_phone", ""),
        "work_start": st.get("work_start", "09:00"),
        "max_hours": st.get("max_hours", "8"),
    }


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(require_dispatcher)):
    orders = db.query(Order).all()
    vehicles = db.query(Vehicle).all()
    routes = db.query(Route).options(joinedload(Route.vehicle), joinedload(Route.stops).joinedload(RouteStop.order)).all()
    uns = db.query(Unassigned).all()
    assigned_ids = {s.order_id for r in routes for s in r.stops}
    un_ids = {u.order_id for u in uns}
    st = settings_map(db)
    vehicles_by_id = {v.id: v for v in vehicles}
    costs = fleet_costs(routes, vehicles_by_id, st)
    order_route = {}
    for r in routes:
        for s in r.stops:
            order_route[s.order_id] = {"vehicle": vehicle_dict(r.vehicle), "eta": s.eta, "status": s.status, "seq": s.seq}
    return {
        "kpis": {
            "orders": len(orders),
            "weight": sum(o.weight_kg for o in orders),
            "vehicles": len(vehicles),
            "active_vehicles": sum(1 for v in vehicles if v.is_active),
            "assigned": len(assigned_ids),
            "unassigned": len(un_ids),
            "unique_addresses": len({(o.address or "").strip().lower() for o in orders if o.address}),
            "with_windows": sum(1 for o in orders if o.preferred_time or o.window_start),
            "distance_m": int(round(costs["fleet_km"] * 1000)),
            "duration_s": sum(r.duration_s for r in routes),
            "driver_hours": costs["driver_hours"],
        },
        "costs": costs,
        "depot": depot_dict(st),
        "vehicles": [vehicle_dict(v) for v in vehicles],
        "orders": [order_dict(o, {"assignment": order_route.get(o.id)}) for o in orders],
        "routes": [route_dict(r) for r in routes],
        "unassigned": [
            {
                "id": u.id,
                "order_id": u.order_id,
                "reason": u.reason,
                "conflicts": u.conflicts,
                "suggestions": u.suggestions,
                "order": order_dict(next((o for o in orders if o.id == u.order_id), None)) if any(o.id == u.order_id for o in orders) else None,
            }
            for u in uns
        ],
        "restrictions_geometry": historic_forbidden_geometry(),
        "settings": st,
        "drivers": [_driver_live(db, u) for u in db.query(User).filter(User.role == "driver").order_by(User.id).all()],
        "driver_positions": [
            {
                "user_id": u.id,
                "name": u.full_name or u.username,
                "vehicle_id": u.vehicle_id,
                "lat": u.last_lat,
                "lon": u.last_lon,
                "at": u.last_geo_at.isoformat() if u.last_geo_at else None,
                "shift_status": u.shift_status,
            }
            for u in db.query(User).filter(User.role == "driver", User.last_lat.isnot(None)).all()
        ],
    }


@router.post("/routes/solve")
def solve_routes(db: Session = Depends(get_db), user: User = Depends(require_dispatcher)):
    if db.query(Order).count() == 0:
        raise HTTPException(400, "Сначала загрузите заказы из Excel")
    result = run_solver(db)
    routes = db.query(Route).options(joinedload(Route.vehicle), joinedload(Route.stops).joinedload(RouteStop.order)).all()
    uns = db.query(Unassigned).all()
    orders = {o.id: o for o in db.query(Order).all()}
    return {
        "elapsed_s": result.elapsed_s,
        "used_ortools": result.used_ortools,
        "notes": result.notes,
        "total_distance_m": result.total_distance_m,
        "routes": [route_dict(r) for r in routes],
        "unassigned": [
            {
                "order_id": u.order_id,
                "reason": u.reason,
                "conflicts": u.conflicts,
                "suggestions": u.suggestions,
                "order": order_dict(orders[u.order_id]) if u.order_id in orders else None,
            }
            for u in uns
        ],
    }


@router.post("/routes/reassign")
def reassign(body: ReassignIn, db: Session = Depends(get_db), user: User = Depends(require_dispatcher)):
    order = db.get(Order, body.order_id)
    vehicle = db.get(Vehicle, body.vehicle_id)
    if not order or not vehicle:
        raise HTTPException(404, "Заказ или автомобиль не найдены")
    restrictions = db.query(RoadRestriction).all()
    ok, why = vehicle_allowed(vehicle, order, restrictions)
    if not ok:
        raise HTTPException(400, why)
    dest = db.query(Route).filter(Route.vehicle_id == vehicle.id).first()
    if not dest:
        dest = Route(vehicle_id=vehicle.id, status="planned")
        db.add(dest)
        db.flush()
    old_stop = db.query(RouteStop).filter(RouteStop.order_id == order.id).first()
    if old_stop:
        db.delete(old_stop)
    seq = (db.query(RouteStop).filter(RouteStop.route_id == dest.id).count() or 0) + 1
    db.add(RouteStop(route_id=dest.id, order_id=order.id, seq=seq, status="pending"))
    db.commit()
    load = 0
    for s in db.query(RouteStop).filter(RouteStop.route_id == dest.id).all():
        o = db.get(Order, s.order_id)
        load += o.weight_kg if o else 0
    if load > vehicle.capacity_kg:
        raise HTTPException(400, f"Превышение грузоподъёмности: {load} > {vehicle.capacity_kg}")
    dest.load_kg = load
    db.commit()
    return {"ok": True, "warning": "Переназначено вручную. Рекомендуется пересчитать маршруты."}


@router.get("/orders")
def list_orders(db: Session = Depends(get_db), user: User = Depends(require_dispatcher)):
    routes = db.query(Route).options(joinedload(Route.vehicle), joinedload(Route.stops)).all()
    assign = {}
    for r in routes:
        for s in r.stops:
            assign[s.order_id] = {"vehicle": vehicle_dict(r.vehicle) if r.vehicle else None, "status": s.status, "eta": s.eta, "seq": s.seq}
    return [order_dict(o, {"assignment": assign.get(o.id)}) for o in db.query(Order).order_by(Order.id).all()]


@router.post("/orders")
def create_order(body: OrderPatch, db: Session = Depends(get_db), user: User = Depends(require_dispatcher)):
    if not body.name or not body.address:
        raise HTTPException(400, "Нужны название и адрес")
    lat, lon, src = run_coro_sync(resolve_address_coords(body.address))
    from .services.geo import is_historic_address

    o = Order(
        name=body.name,
        address=body.address,
        weight_kg=body.weight_kg or 0,
        preferred_time=body.preferred_time,
        window_start=body.window_start,
        window_end=body.window_end,
        unload_min=body.unload_min,
        lat=body.lat or lat,
        lon=body.lon or lon,
        geo_source=src,
        restricted_historic=is_historic_address(body.address),
    )
    db.add(o)
    db.commit()
    db.refresh(o)
    return order_dict(o)


@router.post("/orders/regeocode")
async def regeocode_orders(db: Session = Depends(get_db), user: User = Depends(require_dispatcher)):
    """Пересчитать координаты заказов через Яндекс.Геокодер. OSM не используем."""
    orders = db.query(Order).order_by(Order.id).all()
    stats = await apply_geocode_to_orders(orders, db=db)
    return {"ok": True, **stats}


@router.post("/orders/apply-coords")
def apply_order_coords(body: OrderCoordsIn, db: Session = Depends(get_db), user: User = Depends(require_dispatcher)):
    """Координаты с Яндекс.Карт (JS-геокодер в браузере) — точные дома."""
    n = 0
    for it in body.items:
        if not in_grodno(it.lat, it.lon):
            continue
        o = db.get(Order, it.id)
        if not o:
            continue
        o.lat = it.lat
        o.lon = it.lon
        o.geo_source = it.source or "yandex"
        warn_parts = [p for p in (o.warning or "").split("; ") if p and "Координаты" not in p]
        o.warning = "; ".join(warn_parts)
        n += 1
    db.commit()
    return {"ok": True, "updated": n}


@router.delete("/orders/{oid}")
def delete_order(oid: int, db: Session = Depends(get_db), user: User = Depends(require_dispatcher)):
    o = db.get(Order, oid)
    if not o:
        raise HTTPException(404, "Заказ не найден")
    db.query(RouteStop).filter(RouteStop.order_id == oid).delete()
    db.query(Unassigned).filter(Unassigned.order_id == oid).delete()
    db.delete(o)
    db.commit()
    return {"ok": True}


@router.patch("/orders/{oid}")
def patch_order(oid: int, body: OrderPatch, db: Session = Depends(get_db), user: User = Depends(require_dispatcher)):
    o = db.get(Order, oid)
    if not o:
        raise HTTPException(404, "Заказ не найден")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(o, k, v)
    if "address" in data and ("lat" not in data or "lon" not in data):
        lat, lon, src = run_coro_sync(resolve_address_coords(o.address))
        o.lat, o.lon, o.geo_source = lat, lon, src
        from .services.geo import is_historic_address

        o.restricted_historic = is_historic_address(o.address)
    db.commit()
    return order_dict(o)


@router.post("/import/excel")
async def import_excel(
    file: UploadFile | None = File(None),
    preview: bool = Query(False),
    replace: bool = Query(True),
    db: Session = Depends(get_db),
    user: User = Depends(require_dispatcher),
):
    path = EXCEL_PATH
    if file is not None:
        dest = EXCEL_PATH.parent / "upload.xlsx"
        dest.write_bytes(await file.read())
        path = dest
    if not path.exists():
        raise HTTPException(400, "Файл Excel не найден")
    name = (file.filename if file else path.name) or ""
    if not name.lower().endswith((".xlsx", ".xls")) and file is not None:
        raise HTTPException(400, "Нужен файл Excel (.xlsx)")
    if preview:
        prev = preview_workbook(path)
        prev["existing_orders"] = db.query(Order).count()
        prev["replace"] = replace
        return prev
    if replace and db.query(Order).count() and not preview:
        pass
    info = import_workbook(db, path, replace=replace)
    solve_payload = None
    if db.query(Order).count() > 0:
        result = run_solver(db)
        active_n = db.query(Vehicle).filter(Vehicle.is_active).count()
        used_vehicles = len({r.vehicle_id for r in result.routes})
        solve_payload = {
            "routes": len(result.routes),
            "vehicles_used": used_vehicles,
            "vehicles_idle": max(0, active_n - used_vehicles),
            "unassigned": len(result.unassigned),
            "total_distance_m": result.total_distance_m,
            "elapsed_s": round(result.elapsed_s, 2),
            "notes": result.notes,
        }
    return {
        "imported": info["imported"],
        "duplicates": info["duplicates"],
        "historic": info["historic"],
        "total_weight": info["total_weight"],
        "errors": info["errors"],
        "orders": [order_dict(o) for o in info["orders"]],
        "solve": solve_payload,
    }


@router.get("/vehicles")
def list_vehicles(db: Session = Depends(get_db), user: User = Depends(require_dispatcher)):
    drivers = {u.vehicle_id: u for u in db.query(User).filter(User.role == "driver").all() if u.vehicle_id}
    routes = {r.vehicle_id: r for r in db.query(Route).options(joinedload(Route.stops)).all()}
    out = []
    for v in db.query(Vehicle).order_by(Vehicle.id).all():
        r = routes.get(v.id)
        d = drivers.get(v.id)
        extra = {
            "driver_name": d.full_name if d else None,
            "driver_username": d.username if d else None,
            "orders_count": len(r.stops) if r else 0,
            "load_kg": r.load_kg if r else 0,
            "fill": (r.load_kg / v.capacity_kg) if r and v.capacity_kg else 0,
            "route_id": r.id if r else None,
            "distance_m": r.distance_m if r else 0,
            "duration_s": r.duration_s if r else 0,
        }
        out.append(vehicle_dict(v, extra))
    return out


@router.get("/vehicles/{vid}")
def get_vehicle(vid: int, db: Session = Depends(get_db), user: User = Depends(require_dispatcher)):
    v = db.get(Vehicle, vid)
    if not v:
        raise HTTPException(404)
    d = db.query(User).filter(User.role == "driver", User.vehicle_id == vid).first()
    r = (
        db.query(Route)
        .options(joinedload(Route.stops).joinedload(RouteStop.order), joinedload(Route.vehicle))
        .filter(Route.vehicle_id == vid)
        .order_by(Route.id.desc())
        .first()
    )
    historic = []
    if r:
        historic = [stop_dict(s) for s in r.stops if s.order and s.order.restricted_historic]
    return {
        "vehicle": vehicle_dict(v, {"driver_name": d.full_name if d else None, "driver_username": d.username if d else None}),
        "route": route_dict(r) if r else None,
        "mandatory_stops": historic,
        "depot": depot_dict(settings_map(db)),
    }


@router.post("/vehicles")
def create_vehicle(body: VehicleIn, db: Session = Depends(get_db), user: User = Depends(require_dispatcher)):
    v = Vehicle(**body.model_dump())
    db.add(v)
    db.commit()
    db.refresh(v)
    n = db.query(User).filter(User.role == "driver", User.vehicle_id == None).count()  # noqa: E711
    db.add(User(username=f"driver_{v.plate.replace(' ', '')}", password_hash=hash_password("driver"), full_name=f"Водитель {v.plate}", role="driver", vehicle_id=v.id))
    db.commit()
    return vehicle_dict(v)


@router.patch("/vehicles/{vid}")
def patch_vehicle(vid: int, body: dict, db: Session = Depends(get_db), user: User = Depends(require_dispatcher)):
    v = db.get(Vehicle, vid)
    if not v:
        raise HTTPException(404)
    nums = {"capacity_kg": int, "max_mass_kg": int, "height_m": float, "width_m": float, "length_m": float}
    for k, val in body.items():
        if k in {"id", "title"}:
            continue
        if k in nums and val not in (None, ""):
            val = nums[k](val)
        if hasattr(v, k):
            setattr(v, k, val)
    db.commit()
    return vehicle_dict(v)


@router.delete("/vehicles/{vid}")
def delete_vehicle(vid: int, db: Session = Depends(get_db), user: User = Depends(require_dispatcher)):
    v = db.get(Vehicle, vid)
    if not v:
        raise HTTPException(404)
    db.query(User).filter(User.vehicle_id == vid).delete()
    db.delete(v)
    db.commit()
    return {"ok": True}


@router.get("/restrictions")
def list_rest(db: Session = Depends(get_db), user: User = Depends(require_dispatcher)):
    return [restriction_dict(r) for r in db.query(RoadRestriction).all()]


@router.post("/restrictions")
def add_rest(body: RestrictionIn, db: Session = Depends(get_db), user: User = Depends(require_dispatcher)):
    r = RoadRestriction(**body.model_dump())
    db.add(r)
    db.commit()
    db.refresh(r)
    return restriction_dict(r)


@router.patch("/restrictions/{rid}")
def patch_rest(rid: int, body: dict, db: Session = Depends(get_db), user: User = Depends(require_dispatcher)):
    r = db.get(RoadRestriction, rid)
    if not r:
        raise HTTPException(404)
    for k, val in body.items():
        if hasattr(r, k) and k != "id":
            setattr(r, k, val)
    db.commit()
    return restriction_dict(r)


@router.get("/feasibility")
def feasibility(db: Session = Depends(get_db), user: User = Depends(require_dispatcher)):
    orders = db.query(Order).all()
    vehicles = [v for v in db.query(Vehicle).all() if v.is_active]
    restrictions = [r for r in db.query(RoadRestriction).all() if r.is_active]
    st = settings_map(db)
    demand = sum(o.weight_kg for o in orders)
    cap = sum(v.capacity_kg for v in vehicles)
    hist = [o for o in orders if o.restricted_historic]
    hist_cap = sum(v.capacity_kg for v in vehicles if v.capacity_kg <= 1500)
    warns = []
    if demand > cap:
        warns.append(f"Спрос {demand} кг превышает ёмкость парка {cap} кг")
    if hist and hist_cap < sum(o.weight_kg for o in hist):
        warns.append("Заказов в историческом центре больше, чем вмещает 1,5 т")
    if not vehicles:
        warns.append("Нет активных автомобилей")
    if not orders:
        warns.append("Нет заказов — загрузите Excel")
    try:
        max_trips = max(1, min(10, int(float(st.get("max_trips", "3")))))
    except (TypeError, ValueError):
        max_trips = 3
    max_fill = float(st.get("max_fill", "1") or "1")
    trip_slots = len(vehicles) * max_trips if vehicles else 0
    avg_cap = cap / len(vehicles) if vehicles else 0
    est_routes = max(1, math.ceil(demand / max(1, avg_cap * max_fill))) if avg_cap else 1
    est_routes = min(est_routes, trip_slots) if trip_slots else est_routes
    if trip_slots and est_routes > trip_slots:
        warns.append(
            f"Оценка {est_routes} рейсов при лимите {max_trips}/маш. ({trip_slots} слотов) — часть заказов может остаться"
        )
    return {
        "orders": len(orders),
        "weight": demand,
        "capacity": cap,
        "reserve_kg": cap - demand,
        "vehicles": len(vehicles),
        "restrictions": len(restrictions),
        "historic_orders": len(hist),
        "min_fill": st.get("min_fill", "0.9"),
        "max_trips": max_trips,
        "est_route_trips": est_routes,
        "trip_slots": trip_slots,
        "warnings": warns,
    }


@router.post("/routes/rebuild-geometries")
async def rebuild_all_geometries(db: Session = Depends(get_db), user: User = Depends(require_dispatcher)):
    """Пересчитать линии рейсов по дорогам (OSRM / Яндекс Routing) для всего парка."""
    if not route_geometry_enabled():
        raise HTTPException(
            503,
            "Геометрия отключена (SKIP_ROUTE_GEOMETRY=1 на сервере). Установите 0 и перезапустите API.",
        )
    await fill_route_geometries(db)
    n = db.query(Route).count()
    return {"ok": True, "routes": n}


@router.post("/routes/{rid}/rebuild")
async def rebuild_route(rid: int, db: Session = Depends(get_db), user: User = Depends(require_dispatcher)):
    r = db.query(Route).options(joinedload(Route.stops).joinedload(RouteStop.order)).filter(Route.id == rid).first()
    if not r:
        raise HTTPException(404)
    st = settings_map(db)
    pts = route_waypoints(r, depot_tuple(st))
    line = await road_polyline(pts)
    r.geometry_json = json.dumps(line, ensure_ascii=False)
    db.commit()
    return {"ok": True, "points": len(line), "line": line}


@router.delete("/restrictions/{rid}")
def del_rest(rid: int, db: Session = Depends(get_db), user: User = Depends(require_dispatcher)):
    r = db.get(RoadRestriction, rid)
    if r:
        db.delete(r)
        db.commit()
    return {"ok": True}


@router.get("/settings")
def get_settings(db: Session = Depends(get_db), user: User = Depends(require_dispatcher)):
    return settings_map(db)


@router.put("/settings")
def put_settings(body: dict, db: Session = Depends(get_db), user: User = Depends(require_dispatcher)):
    for k, v in body.items():
        row = db.get(Setting, k)
        if row:
            row.value = str(v)
        else:
            db.add(Setting(key=k, value=str(v)))
    db.commit()
    return settings_map(db)


@router.get("/drivers")
def list_drivers(db: Session = Depends(get_db), user: User = Depends(require_dispatcher)):
    return [_driver_live(db, u) for u in db.query(User).filter(User.role == "driver").order_by(User.id).all()]


@router.post("/drivers")
def create_driver(body: DriverCreateIn, db: Session = Depends(get_db), user: User = Depends(require_dispatcher)):
    username = (body.username or "").strip()
    if not username:
        raise HTTPException(400, "Укажите логин")
    if not (body.password or "").strip():
        raise HTTPException(400, "Укажите пароль")
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(400, "Такой логин уже занят")
    phone = _norm_phone(body.phone)
    if phone and db.query(User).filter(User.phone == phone).first():
        raise HTTPException(400, "Такой телефон уже зарегистрирован")
    vehicle_id = body.vehicle_id or None
    if vehicle_id and not db.get(Vehicle, vehicle_id):
        raise HTTPException(404, "Автомобиль не найден")
    _assert_vehicle_free(db, vehicle_id)
    row = User(
        username=username,
        password_hash=hash_password(body.password),
        full_name=(body.full_name or "").strip(),
        phone=phone,
        role="driver",
        vehicle_id=vehicle_id,
        is_active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _driver_live(db, row)


@router.patch("/drivers/{uid}")
def patch_driver(uid: int, body: DriverPatchIn, db: Session = Depends(get_db), user: User = Depends(require_dispatcher)):
    row = db.get(User, uid)
    if not row or row.role != "driver":
        raise HTTPException(404, "Водитель не найден")
    data = body.model_dump(exclude_unset=True)
    if "username" in data and data["username"] is not None:
        username = data["username"].strip()
        if not username:
            raise HTTPException(400, "Логин не может быть пустым")
        clash = db.query(User).filter(User.username == username, User.id != uid).first()
        if clash:
            raise HTTPException(400, "Такой логин уже занят")
        row.username = username
    if "full_name" in data and data["full_name"] is not None:
        row.full_name = data["full_name"].strip()
    if "phone" in data and data["phone"] is not None:
        phone = _norm_phone(data["phone"])
        if phone:
            clash = db.query(User).filter(User.phone == phone, User.id != uid).first()
            if clash:
                raise HTTPException(400, "Такой телефон уже зарегистрирован")
        row.phone = phone
    if "vehicle_id" in data:
        vid = data["vehicle_id"] or None
        if vid and not db.get(Vehicle, vid):
            raise HTTPException(404, "Автомобиль не найден")
        _assert_vehicle_free(db, vid, except_user_id=uid)
        row.vehicle_id = vid
    if "is_active" in data and data["is_active"] is not None:
        row.is_active = bool(data["is_active"])
        if not row.is_active:
            row.vehicle_id = row.vehicle_id
    if data.get("password"):
        row.password_hash = hash_password(data["password"])
    db.commit()
    db.refresh(row)
    return _driver_live(db, row)


@router.delete("/drivers/{uid}")
def delete_driver(uid: int, db: Session = Depends(get_db), user: User = Depends(require_dispatcher)):
    """Деактивирует аккаунт. Маршруты и история доставок остаются у автомобиля."""
    row = db.get(User, uid)
    if not row or row.role != "driver":
        raise HTTPException(404, "Водитель не найден")
    row.is_active = False
    row.vehicle_id = None
    db.commit()
    return {"ok": True, "deactivated": True}


@router.get("/driver/route")
def driver_route(db: Session = Depends(get_db), user: User = Depends(require_driver)):
    st = settings_map(db)
    if not user.vehicle_id:
        return {
            "driver": user_dict(user),
            "depot": depot_dict(st),
            "vehicle": None,
            "route": None,
            "routes": [],
            "message": "Автомобиль не назначен. Обратитесь к диспетчеру",
        }
    v = db.get(Vehicle, user.vehicle_id)
    routes = (
        db.query(Route)
        .options(joinedload(Route.stops).joinedload(RouteStop.order), joinedload(Route.vehicle))
        .filter(Route.vehicle_id == user.vehicle_id)
        .order_by(Route.id)
        .all()
    )
    current = next((r for r in routes if any(s.status not in ("done", "problem") for s in r.stops)), None)
    if current is None:
        current = routes[-1] if routes else None
    stops = [s for r in routes for s in r.stops]
    _refresh_shift(user, stops)
    remaining_kg = sum((s.order.weight_kg if s.order else 0) for s in stops if s.status not in ("done", "problem"))
    unread = db.query(DriverNotification).filter(DriverNotification.user_id == user.id, DriverNotification.read.is_(False)).count()
    db.commit()
    return {
        "driver": user_dict(user),
        "depot": depot_dict(st),
        "vehicle": vehicle_dict(v, {"load_kg": sum(r.load_kg for r in routes), "remaining_kg": remaining_kg}) if v else None,
        "route": route_dict(current) if current else None,
        "routes": [route_dict(r) for r in routes],
        "work_start": st.get("work_start", "09:00"),
        "max_hours": st.get("max_hours", "8"),
        "dispatcher_name": st.get("dispatcher_name", "Диспетчер логистики"),
        "dispatcher_phone": st.get("dispatcher_phone", ""),
        "unread_notifications": unread,
        "message": None if v else "Автомобиль не назначен. Обратитесь к диспетчеру",
    }


def _apply_event(s: RouteStop, body) -> datetime:
    at = _parse_client_at(getattr(body, "at", None) if body else None)
    lat = getattr(body, "lat", None) if body else None
    lon = getattr(body, "lon", None) if body else None
    if lat is not None and lon is not None:
        s.event_lat = lat
        s.event_lon = lon
    return at


@router.post("/driver/stops/{sid}/start")
def driver_start(
    sid: int,
    body: DriverStartIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_driver),
):
    s = _driver_stop(db, user, sid)
    if s.status == "done":
        return stop_dict(s)
    at = _apply_event(s, body)
    if body and body.arrive:
        s.status = "at_stop"
        if not s.started_at:
            s.started_at = at
        if not user.shift_started_at:
            user.shift_started_at = at
        user.shift_status = "at_stop"
    else:
        s.status = "enroute"
        user.shift_status = "on_route"
        if not user.shift_started_at:
            user.shift_started_at = at
    db.commit()
    return stop_dict(s)


@router.post("/driver/stops/{sid}/arrive")
def driver_arrive(sid: int, body: StopEventIn | None = None, db: Session = Depends(get_db), user: User = Depends(require_driver)):
    s = _driver_stop(db, user, sid)
    if s.status == "done":
        return stop_dict(s)
    at = _apply_event(s, body)
    s.status = "at_stop"
    if not s.started_at:
        s.started_at = at
    if not user.shift_started_at:
        user.shift_started_at = at
    user.shift_status = "at_stop"
    db.commit()
    return stop_dict(s)


@router.post("/driver/stops/{sid}/unload")
def driver_unload(sid: int, body: StopEventIn | None = None, db: Session = Depends(get_db), user: User = Depends(require_driver)):
    s = _driver_stop(db, user, sid)
    if s.status == "done":
        return stop_dict(s)
    at = _apply_event(s, body)
    if s.status not in ("at_stop", "unloading", "enroute"):
        s.status = "at_stop"
        if not s.started_at:
            s.started_at = at
    s.status = "unloading"
    if not getattr(s, "unloading_started_at", None):
        s.unloading_started_at = at
    user.shift_status = "unloading"
    db.commit()
    return stop_dict(s)


@router.post("/driver/stops/{sid}/done")
def driver_done(sid: int, body: StopEventIn | None = None, db: Session = Depends(get_db), user: User = Depends(require_driver)):
    s = _driver_stop(db, user, sid)
    if s.status == "done":
        return stop_dict(s)
    at = _apply_event(s, body)
    if s.status not in ("at_stop", "unloading", "enroute") and s.started_at is None:
        s.started_at = at
    if body and body.actual_weight_kg is not None:
        s.actual_weight_kg = body.actual_weight_kg
    if body and body.comment:
        s.driver_comment = body.comment
    s.status = "done"
    s.completed_at = at
    db.commit()
    _notify_dispatchers(db, f"done:{s.id}", "Заказ выполнен", f"{user.full_name}: точка {s.seq} выполнена", "done")
    db.commit()
    return stop_dict(s)


@router.post("/driver/stops/{sid}/problem")
def driver_problem(sid: int, body: ProblemIn, db: Session = Depends(get_db), user: User = Depends(require_driver)):
    s = _driver_stop(db, user, sid)
    if s.status == "done":
        raise HTTPException(400, "Доставка уже отмечена выполненной")
    reason = (body.reason or "").strip()
    comment = (body.comment or body.text or "").strip()
    s.status = "problem"
    s.problem_reason = reason
    s.problem_text = f"{reason}: {comment}".strip(": ").strip() if reason else comment
    _apply_event(s, body)
    disp = db.query(User).filter(User.role == "dispatcher").first()
    db.add(
        DriverMessage(
            from_user_id=user.id,
            to_user_id=disp.id if disp else None,
            stop_id=s.id,
            text=s.problem_text,
            kind="problem",
        )
    )
    _notify_dispatchers(db, f"problem:{s.id}", "Проблема на маршруте", f"{user.full_name}: {s.problem_text}", "problem")
    db.commit()
    return stop_dict(s)


def _driver_stop(db: Session, user: User, sid: int) -> RouteStop:
    s = db.get(RouteStop, sid)
    if not s:
        raise HTTPException(404)
    route = db.get(Route, s.route_id)
    if user.role != "driver" or not route or route.vehicle_id != user.vehicle_id:
        raise HTTPException(403, "Это не ваш маршрут")
    return s


@router.post("/driver/geo")
def driver_geo(body: GeoIn, db: Session = Depends(get_db), user: User = Depends(require_driver)):
    if body.enabled is not None:
        user.geo_enabled = body.enabled
    if not user.geo_enabled:
        db.commit()
        return {"ok": True, "enabled": False}
    if user.shift_status in ("waiting", "finished"):
        return {"ok": True, "enabled": True, "tracked": False}
    if body.lat is None or body.lon is None:
        db.commit()
        return {"ok": True, "enabled": True, "tracked": False}
    user.last_lat = body.lat
    user.last_lon = body.lon
    user.last_geo_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "enabled": True, "tracked": True, "at": user.last_geo_at.isoformat()}


@router.patch("/driver/shift")
def driver_shift(body: ShiftIn, db: Session = Depends(get_db), user: User = Depends(require_driver)):
    allowed = {"waiting", "ready", "on_route", "at_stop", "unloading", "break", "returning", "finished"}
    if body.status not in allowed:
        raise HTTPException(400, "Неизвестный статус смены")
    if body.status == "finished":
        stops = []
        if user.vehicle_id:
            routes = db.query(Route).options(joinedload(Route.stops)).filter(Route.vehicle_id == user.vehicle_id).all()
            stops = [s for r in routes for s in r.stops]
        open_n = sum(1 for s in stops if s.status not in ("done", "problem"))
        if open_n:
            raise HTTPException(400, f"Нельзя завершить смену: осталось {open_n} незакрытых заказов")
        user.shift_ended_at = datetime.utcnow()
    if body.status == "ready" and not user.shift_started_at:
        user.shift_started_at = datetime.utcnow()
    user.shift_status = body.status
    db.commit()
    return user_dict(user)


@router.get("/driver/messages")
def driver_messages(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(DriverMessage).order_by(DriverMessage.created_at.desc()).limit(80)
    if user.role == "driver":
        q = q.filter((DriverMessage.from_user_id == user.id) | (DriverMessage.to_user_id == user.id))
    rows = list(reversed(q.all()))
    users = {u.id: u for u in db.query(User).all()}
    return [
        {
            "id": m.id,
            "from_user_id": m.from_user_id,
            "from_name": (users.get(m.from_user_id).full_name if users.get(m.from_user_id) else "") or "",
            "to_user_id": m.to_user_id,
            "text": m.text,
            "kind": m.kind,
            "stop_id": m.stop_id,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "mine": m.from_user_id == user.id,
        }
        for m in rows
    ]


@router.post("/driver/messages")
def post_driver_message(body: ChatIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(400, "Пустое сообщение")
    if user.role != "driver":
        raise HTTPException(403, "Для ответа водителю используйте карточку водителя")
    disp = db.query(User).filter(User.role == "dispatcher", User.is_active.is_(True)).first()
    to_id = disp.id if disp else None
    _notify_dispatchers(db, f"chat:{user.id}:{int(datetime.utcnow().timestamp())}", "Сообщение от водителя", f"{user.full_name}: {text[:180]}", "chat")
    db.add(DriverMessage(from_user_id=user.id, to_user_id=to_id, stop_id=body.stop_id, text=text, kind="chat"))
    db.commit()
    return {"ok": True}


@router.post("/drivers/{uid}/messages")
def dispatcher_to_driver(uid: int, body: ChatIn, db: Session = Depends(get_db), user: User = Depends(require_dispatcher)):
    drv = db.get(User, uid)
    if not drv or drv.role != "driver":
        raise HTTPException(404, "Водитель не найден")
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(400, "Пустое сообщение")
    db.add(DriverMessage(from_user_id=user.id, to_user_id=drv.id, stop_id=body.stop_id, text=text, kind="chat"))
    _notify(db, drv.id, f"chatd:{int(datetime.utcnow().timestamp())}", "Сообщение диспетчера", text[:200], "chat")
    db.commit()
    return {"ok": True}


@router.patch("/driver/stops/{sid}/reply")
def dispatcher_reply_problem(sid: int, body: ProblemReplyIn, db: Session = Depends(get_db), user: User = Depends(require_dispatcher)):
    s = db.get(RouteStop, sid)
    if not s:
        raise HTTPException(404)
    s.dispatcher_reply = body.reply
    route = db.get(Route, s.route_id)
    drv = db.query(User).filter(User.role == "driver", User.vehicle_id == route.vehicle_id).first() if route else None
    if drv:
        _notify(db, drv.id, f"reply:{s.id}", "Ответ диспетчера", body.reply, "chat")
    db.commit()
    return stop_dict(s)


@router.get("/driver/notifications")
def list_notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (
        db.query(DriverNotification)
        .filter(DriverNotification.user_id == user.id)
        .order_by(DriverNotification.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": n.id,
            "title": n.title,
            "body": n.body,
            "kind": n.kind,
            "read": n.read,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in rows
    ]


@router.post("/driver/notifications/read")
def read_notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.query(DriverNotification).filter(DriverNotification.user_id == user.id, DriverNotification.read.is_(False)).update({"read": True})
    db.commit()
    return {"ok": True}


@router.get("/driver/history")
def driver_history(db: Session = Depends(get_db), user: User = Depends(require_driver)):
    rows = (
        db.query(TripArchive)
        .filter((TripArchive.driver_id == user.id) | ((TripArchive.vehicle_id == user.vehicle_id) & (TripArchive.vehicle_id.isnot(None))))
        .order_by(TripArchive.id.desc())
        .limit(30)
        .all()
    )
    return [
        {
            "id": t.id,
            "date": t.route_date,
            "plate": t.plate,
            "orders": t.orders_n,
            "done": t.done_n,
            "problem": t.problem_n,
            "weight_kg": t.weight_kg,
            "distance_m": t.distance_m,
            "started": t.started_at,
            "finished": t.finished_at,
            "detail": json.loads(t.detail_json) if t.detail_json else {},
        }
        for t in rows
    ]


@router.get("/analytics")
def analytics(db: Session = Depends(get_db), user: User = Depends(require_dispatcher)):
    routes = db.query(Route).options(joinedload(Route.vehicle), joinedload(Route.stops).joinedload(RouteStop.order)).all()
    st = settings_map(db)
    vehicles_by_id = {v.id: v for v in db.query(Vehicle).all()}
    costs = fleet_costs(routes, vehicles_by_id, st)
    stops = [s for r in routes for s in r.stops]
    done = [s for s in stops if s.status == "done"]
    late = 0
    for s in done:
        if s.completed_at and s.eta:
            hh, mm = map(int, s.eta.split(":"))
            plan = hh * 60 + mm
            act = s.completed_at.hour * 60 + s.completed_at.minute
            if act > plan + 10:
                late += 1
    per_vehicle = []
    for row in costs["per_vehicle"]:
        r = next((x for x in routes if x.id == row["route_id"]), None)
        if not r:
            continue
        v = r.vehicle
        per_vehicle.append(
            {
                "plate": row["plate"],
                "color": v.color if v else "#888",
                "km": row["km"],
                "fill": round(r.load_kg / v.capacity_kg * 100, 1) if v and v.capacity_kg else 0,
                "hours": row["hours"],
                "stops": len(r.stops),
                "done": sum(1 for s in r.stops if s.status == "done"),
                "load_kg": r.load_kg,
                "capacity": v.capacity_kg if v else 0,
                "cost": row["cost"],
                "fuel_l": row["fuel_l"],
            }
        )
    done_pct = round(100 * len(done) / len(stops), 1) if stops else 0
    return {
        "fleet_km": costs["fleet_km"],
        "fleet_km_plan": costs["fleet_km_plan"],
        "fleet_km_roads": costs["fleet_km_roads"],
        "cost_byn": costs["cost_byn"],
        "fuel_cost_byn": costs["fuel_cost_byn"],
        "fuel_l": costs["fuel_l"],
        "fuel_price_byn": costs["fuel_price_byn"],
        "fuel_l_per_100km": costs["fuel_l_per_100km"],
        "cost_basis": costs["cost_basis"],
        "hours": costs["driver_hours"],
        "deliveries_done": len(done),
        "deliveries_total": len(stops),
        "done_pct": done_pct,
        "late": late,
        "vehicles_used": len({r.vehicle_id for r in routes}),
        "route_trips": len(routes),
        "avg_fill": round(sum(p["fill"] for p in per_vehicle) / len(per_vehicle), 1) if per_vehicle else 0,
        "per_vehicle": per_vehicle,
        "has_history": False,
    }


@router.get("/routes/{rid}/geometry")
async def geom(rid: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    r = db.query(Route).options(joinedload(Route.stops).joinedload(RouteStop.order)).filter(Route.id == rid).first()
    if not r:
        raise HTTPException(404)
    if user.role == "driver" and r.vehicle_id != user.vehicle_id:
        raise HTTPException(403, "Это не ваш маршрут")
    st = settings_map(db)
    depot = depot_tuple(st)
    pts = route_waypoints(r, depot)
    line = await road_polyline(pts)
    return {"line": line}
