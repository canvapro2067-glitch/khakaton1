import re
from datetime import datetime

from openpyxl import load_workbook
from sqlalchemy.orm import Session

from ..async_util import run_coro_sync
from ..models import Order
from .geo import is_historic_address
from .geocode_resolve import resolve_many

SKIP_ADDR = {"общий объем, кг", "общий объем"}
SKIP_ORG_PREFIX = ("транспорт", "грузоподъемность", "загрузка", "торговые объекты", "весь транспорт", "для наиболее", "необходимо скоратить", "необходимо сократить", "тоннаж на каждый", "рабочий день")


def parse_time_cell(value) -> str | None:
    if value is None:
        return None
    s = str(value).strip().lower().replace(".", ":").replace("–", "-").replace("—", "-")
    m = re.search(r"(\d{1,2})\s*[-:]\s*(\d{2})", s)
    if m:
        return f"{int(m.group(1)):02d}:{m.group(2)}"
    m = re.search(r"(\d{1,2}):(\d{2})", s)
    if m:
        return f"{int(m.group(1)):02d}:{m.group(2)}"
    return None


def parse_excel_rows(path) -> tuple[list, list]:
    wb = load_workbook(path, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = []
    errors = []
    for i, row in enumerate(ws.iter_rows(values_only=True), 1):
        org = (row[0] or "") if row else ""
        addr = (row[1] or "") if row and len(row) > 1 else ""
        ton = row[2] if row and len(row) > 2 else None
        tcell = row[3] if row and len(row) > 3 else None
        org_s = str(org).strip() if org else ""
        addr_s = str(addr).strip() if addr else ""
        if not org_s and not addr_s:
            continue
        if addr_s.lower() in SKIP_ADDR:
            continue
        low = org_s.lower()
        if any(low.startswith(p) for p in SKIP_ORG_PREFIX) or "грузоподъемность" in low:
            continue
        if org_s.lower() in {"организация"}:
            continue
        if not addr_s:
            continue
        if not org_s:
            errors.append({"row": i, "error": "Пустое название организации", "address": addr_s})
            continue
        try:
            weight = int(round(float(ton)))
        except (TypeError, ValueError):
            errors.append({"row": i, "name": org_s, "error": "Некорректный тоннаж", "raw": str(ton)})
            continue
        if weight <= 0:
            errors.append({"row": i, "name": org_s, "error": "Тоннаж должен быть > 0"})
            continue
        rows.append({"row": i, "name": org_s, "address": addr_s, "weight_kg": weight, "preferred_time": parse_time_cell(tcell)})
    seen: dict[tuple[str, str], int] = {}
    for rec in rows:
        key = (rec["name"].strip().lower(), rec["address"].strip().lower())
        rec["is_duplicate"] = key in seen
        seen[key] = seen.get(key, 0) + 1
    return rows, errors


def preview_workbook(path) -> dict:
    rows, errors = parse_excel_rows(path)
    return {
        "count": len(rows),
        "duplicates": sum(1 for r in rows if r["is_duplicate"]),
        "total_weight": sum(r["weight_kg"] for r in rows),
        "with_windows": sum(1 for r in rows if r["preferred_time"]),
        "unique_addresses": len({r["address"].strip().lower() for r in rows}),
        "errors": errors,
        "preview": rows[:40],
    }


def import_workbook(db: Session, path, replace: bool = True) -> dict:
    batch = datetime.now().strftime("%Y%m%d-%H%M%S")
    parsed, errors = parse_excel_rows(path)
    if replace:
        db.query(Order).delete()
        db.commit()

    coords = run_coro_sync(resolve_many([rec["address"] for rec in parsed])) if parsed else []

    created = []
    for rec, (lat, lon, src) in zip(parsed, coords):
        name, address, weight, pref = rec["name"], rec["address"], rec["weight_kg"], rec["preferred_time"]
        dup = rec["is_duplicate"]
        historic = is_historic_address(address)
        warning = []
        if dup:
            warning.append("Возможный дубль (та же организация и адрес)")
        if src not in ("yandex", "osm"):
            warning.append("Координаты приблизительные, рекомендуется проверить")
        order = Order(
            name=name.strip(),
            address=address.strip(),
            weight_kg=weight,
            preferred_time=pref,
            lat=lat,
            lon=lon,
            geo_source=src,
            is_duplicate=dup,
            import_batch=batch,
            warning="; ".join(warning),
            restricted_historic=historic,
        )
        db.add(order)
        created.append(order)
    db.commit()
    for o in created:
        db.refresh(o)
    return {
        "batch": batch,
        "imported": len(created),
        "duplicates": sum(1 for o in created if o.is_duplicate),
        "historic": sum(1 for o in created if o.restricted_historic),
        "total_weight": sum(o.weight_kg for o in created),
        "errors": errors,
        "orders": created,
    }
