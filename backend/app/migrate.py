from sqlalchemy import inspect, text

from .database import engine


def _add_column(table: str, name: str, ddl: str, existing: set[str]) -> None:
    if name in existing:
        return
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))


def ensure_schema() -> None:
    insp = inspect(engine)
    if not insp.has_table("routes"):
        return
    cols = {c["name"] for c in insp.get_columns("routes")}
    _add_column("routes", "geometry_json", "geometry_json TEXT", cols)
    if insp.has_table("settings"):
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE settings SET value = '3' WHERE key = 'max_trips' AND value = '1'")
            )
            conn.execute(
                text("UPDATE settings SET value = '09:00' WHERE key = 'work_start' AND value = '06:00'")
            )
            conn.execute(
                text(
                    "UPDATE settings SET value = '2.89' WHERE key = 'fuel_price_byn' AND value = '2.45'"
                )
            )
    if insp.has_table("users"):
        ucols = {c["name"] for c in insp.get_columns("users")}
        _add_column("users", "phone", "phone VARCHAR(32) DEFAULT ''", ucols)
        _add_column("users", "created_at", "created_at DATETIME", ucols)
        _add_column("users", "last_lat", "last_lat FLOAT", ucols)
        _add_column("users", "last_lon", "last_lon FLOAT", ucols)
        _add_column("users", "last_geo_at", "last_geo_at DATETIME", ucols)
        _add_column("users", "geo_enabled", "geo_enabled BOOLEAN DEFAULT 1", ucols)
        _add_column("users", "shift_status", "shift_status VARCHAR(24) DEFAULT 'waiting'", ucols)
        _add_column("users", "shift_started_at", "shift_started_at DATETIME", ucols)
        _add_column("users", "shift_ended_at", "shift_ended_at DATETIME", ucols)
    if insp.has_table("orders"):
        ocols = {c["name"] for c in insp.get_columns("orders")}
        _add_column("orders", "contact_phone", "contact_phone VARCHAR(40) DEFAULT ''", ocols)
        _add_column("orders", "dispatcher_note", "dispatcher_note TEXT DEFAULT ''", ocols)
    if insp.has_table("route_stops"):
        scols = {c["name"] for c in insp.get_columns("route_stops")}
        _add_column("route_stops", "problem_reason", "problem_reason VARCHAR(160) DEFAULT ''", scols)
        _add_column("route_stops", "unloading_started_at", "unloading_started_at DATETIME", scols)
        _add_column("route_stops", "actual_weight_kg", "actual_weight_kg INTEGER", scols)
        _add_column("route_stops", "driver_comment", "driver_comment TEXT DEFAULT ''", scols)
        _add_column("route_stops", "event_lat", "event_lat FLOAT", scols)
        _add_column("route_stops", "event_lon", "event_lon FLOAT", scols)
        _add_column("route_stops", "dispatcher_reply", "dispatcher_reply TEXT DEFAULT ''", scols)