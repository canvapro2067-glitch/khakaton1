from sqlalchemy.orm import Session

from .auth import hash_password
from .models import RoadRestriction, Setting, User, Vehicle
from .services.geo import DEPOT

LEGACY_DEPOT_ADDRESSES = {
    "г. Гродно, ул. Поповича, 8",
}
LEGACY_DEPOT_LAT = "53.6508"
LEGACY_DEPOT_LON = "23.8576"

VEHICLE_SPECS = [
    ("ГАЗ", "Газель Next City", "1,5 т", 1500, 3500, 2.40, 2.07, 5.45, "#E03131"),
    ("Ford", "Transit 350L", "2,8 т", 2800, 3500, 2.55, 2.12, 6.70, "#F76707"),
    ("МАЗ", "4371 Зубрёнок", "3,7 т", 3700, 7500, 2.70, 2.35, 7.50, "#F59F00"),
    ("МАЗ", "4371 Зубрёнок", "3,7 т", 3700, 7500, 2.70, 2.35, 7.50, "#74B816"),
    ("МАЗ", "4380", "4 т", 4000, 8100, 2.85, 2.40, 7.80, "#12B886"),
    ("МАЗ", "4380", "4 т", 4000, 8100, 2.85, 2.40, 7.80, "#15AABF"),
    ("ГАЗ", "ГАЗон Next", "4 т", 4000, 8700, 2.90, 2.38, 7.90, "#228BE6"),
    ("ГАЗ", "ГАЗон Next", "4 т", 4000, 8700, 2.90, 2.38, 7.90, "#4263EB"),
    ("Hyundai", "HD78", "4 т", 4000, 8000, 2.80, 2.20, 6.90, "#7048E8"),
    ("Mercedes-Benz", "Atego 818", "4,6 т", 4600, 9500, 3.00, 2.45, 8.10, "#BE4BDB"),
    ("Mercedes-Benz", "Atego 818", "4,6 т", 4600, 9500, 3.00, 2.45, 8.10, "#E64980"),
    ("МАЗ", "4371C0", "4,6 т", 4600, 10100, 2.95, 2.48, 8.20, "#C92A2A"),
    ("Isuzu", "NPR75", "4,6 т", 4600, 7500, 2.70, 2.22, 7.20, "#495057"),
    ("Iveco", "Eurocargo 100E", "4,8 т", 4800, 10000, 3.05, 2.50, 8.40, "#2B8A3E"),
    ("МАЗ", "5340", "5 т", 5000, 18500, 3.20, 2.55, 8.80, "#0B7285"),
    ("КАМАЗ", "4308", "5 т", 5000, 15400, 3.15, 2.50, 8.50, "#1C7ED6"),
]

DEFAULT_SETTINGS = {
    "work_start": "09:00",
    "max_hours": "8",
    "window_minutes": "60",
    "unload_minutes": "25",
    "min_fill": "0.9",
    "depot_name": DEPOT["name"],
    "depot_address": DEPOT["address"],
    "depot_lat": f"{DEPOT['lat']:.4f}",
    "depot_lon": f"{DEPOT['lon']:.4f}",
    "fuel_l_per_100km": "18",
    "fuel_price_byn": "2.45",
    "time_cost_byn_per_hour": "22",
    "cost_per_km": "0.45",
    "max_fill": "1.0",
    "max_trips": "3",
    "use_windows": "1",
    "historic_center_rule": "1",
    "minimize_fleet": "1",
    "allow_shared_vehicle": "0",
    "company": "ОАО «Молочный мир»",
    "dispatcher_name": "Диспетчер логистики",
    "dispatcher_phone": "+375152000000",
}


def _set_setting(db: Session, key: str, value: str) -> None:
    row = db.get(Setting, key)
    if row:
        row.value = value
    else:
        db.add(Setting(key=key, value=value))


def sync_depot_settings(db: Session) -> None:
    """Обновить склад в уже развёрнутой БД (раньше был ул. Поповича, 8)."""
    addr = db.get(Setting, "depot_address")
    lat = db.get(Setting, "depot_lat")
    lon = db.get(Setting, "depot_lon")
    legacy = (
        (addr and addr.value in LEGACY_DEPOT_ADDRESSES)
        or (lat and lat.value == LEGACY_DEPOT_LAT)
        or (lon and lon.value == LEGACY_DEPOT_LON)
    )
    if not legacy:
        return
    _set_setting(db, "depot_name", DEPOT["name"])
    _set_setting(db, "depot_address", DEPOT["address"])
    _set_setting(db, "depot_lat", f"{DEPOT['lat']:.4f}")
    _set_setting(db, "depot_lon", f"{DEPOT['lon']:.4f}")
    db.commit()


def seed_if_empty(db: Session) -> None:
    if db.query(Vehicle).count() == 0:
        for i, spec in enumerate(VEHICLE_SPECS, 1):
            brand, model, _, cap, mass, h, w, l, color = spec
            plate = f"{i:02d} MM-4"
            db.add(
                Vehicle(
                    brand=brand,
                    model=model,
                    plate=plate,
                    capacity_kg=cap,
                    max_mass_kg=mass,
                    height_m=h,
                    width_m=w,
                    length_m=l,
                    color=color,
                    is_active=True,
                )
            )
        db.commit()

    if db.query(User).count() == 0:
        db.add(User(username="dispatcher", password_hash=hash_password("dispatcher"), full_name="Диспетчер логистики", role="dispatcher"))
        vehicles = db.query(Vehicle).order_by(Vehicle.id).all()
        for i, v in enumerate(vehicles, 1):
            db.add(
                User(
                    username=f"driver{i}",
                    password_hash=hash_password("driver"),
                    full_name=f"Водитель {v.plate}",
                    phone=f"+37529{2000000 + i}",
                    role="driver",
                    vehicle_id=v.id,
                )
            )
        db.commit()

    if db.query(Setting).count() == 0:
        for k, val in DEFAULT_SETTINGS.items():
            db.add(Setting(key=k, value=val))
        db.commit()

    if db.query(RoadRestriction).count() == 0:
        db.add(
            RoadRestriction(
                name="Исторический центр Гродно (Бел. ПДД / местные ограничения)",
                street_pattern="re:(^|[,\\s])советская([,\\s]|\\d|$)",
                max_capacity_kg=1500,
                max_mass_kg=3500,
                note="Советская — только 1,5 т. Не путать с Советских Пограничников.",
            )
        )
        db.add(
            RoadRestriction(
                name="ул. Мостовая — исторический центр",
                street_pattern="re:(^|[,\\s])мостовая([,\\s]|\\d|$)",
                max_capacity_kg=1500,
                max_mass_kg=3500,
                note="Только автомобиль 1,5 т",
            )
        )
        db.add(
            RoadRestriction(
                name="ул. Замковая — исторический центр",
                street_pattern="re:(^|[,\\s])замковая([,\\s]|\\d|$)",
                max_capacity_kg=1500,
                max_mass_kg=3500,
                note="Только автомобиль 1,5 т",
            )
        )
        db.commit()

    sync_depot_settings(db)
    for i, u in enumerate(db.query(User).filter(User.role == "driver").order_by(User.id).all(), 1):
        if not (u.phone or "").strip():
            u.phone = f"+37529{2000000 + i}"
    for k, val in DEFAULT_SETTINGS.items():
        if db.get(Setting, k) is None:
            db.add(Setting(key=k, value=val))
    unload = db.get(Setting, "unload_minutes")
    if unload and unload.value in {"5", "12"}:
        unload.value = "25"
    db.commit()
