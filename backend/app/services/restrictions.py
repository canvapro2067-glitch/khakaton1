import re

from ..models import Order, RoadRestriction, Vehicle


def _match(pattern: str, address: str) -> bool:
    p = (pattern or "").strip().lower().replace("ё", "е")
    a = (address or "").lower().replace("ё", "е")
    if not p:
        return False
    if p.startswith("re:"):
        return re.search(p[3:], a, re.I) is not None
    return p in a


def vehicle_allowed(vehicle: Vehicle, order: Order, restrictions: list[RoadRestriction]) -> tuple[bool, str]:
    if order.restricted_historic and vehicle.capacity_kg > 1500:
        return False, "Исторический центр (Советская, Мостовая, Замковая) — только автомобиль 1,5 т"
    for r in restrictions:
        if not r.is_active:
            continue
        if not _match(r.street_pattern, order.address):
            continue
        if r.vehicle_id and r.vehicle_id == vehicle.id:
            return False, f"Улица запрещена для {vehicle.plate}: {r.name}"
        if r.vehicle_id:
            continue
        if r.max_capacity_kg and vehicle.capacity_kg > r.max_capacity_kg:
            return False, f"{r.name}: грузоподъёмность > {r.max_capacity_kg} кг"
        if r.max_mass_kg and vehicle.max_mass_kg > r.max_mass_kg:
            return False, f"{r.name}: полная масса > {r.max_mass_kg} кг"
        if r.max_height_m and vehicle.height_m > r.max_height_m:
            return False, f"{r.name}: высота > {r.max_height_m} м"
        if r.max_width_m and vehicle.width_m > r.max_width_m:
            return False, f"{r.name}: ширина > {r.max_width_m} м"
        if r.max_length_m and vehicle.length_m > r.max_length_m:
            return False, f"{r.name}: длина > {r.max_length_m} м"
    return True, ""


def historic_forbidden_geometry():
    return [
        {"street": "Советская", "path": [[53.6758, 23.8298], [53.6802, 23.8328]]},
        {"street": "Мостовая", "path": [[53.6778, 23.8268], [53.6796, 23.8310]]},
        {"street": "Замковая", "path": [[53.6762, 23.8238], [53.6786, 23.8272]]},
    ]
