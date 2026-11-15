import os
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import router, run_solver
from .config import CORS_ORIGINS, EXCEL_PATH, YANDEX_MAPS_API_KEY, route_geometry_enabled
from .database import Base, SessionLocal, engine
from .migrate import ensure_schema
from .models import Order, Route
from .seed import seed_if_empty
from .services.excel_import import import_workbook

app = FastAPI(title="Молочный мир — логистика", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    ensure_schema()
    db = SessionLocal()
    try:
        seed_if_empty(db)
        if db.query(Order).count() == 0 and EXCEL_PATH.exists():
            import_workbook(db, EXCEL_PATH, replace=True)
            if os.getenv("SKIP_STARTUP_SOLVE", "").lower() not in ("1", "true", "yes"):
                run_solver(db, fill_geometry=False)
        if db.query(Route).count() == 0 and db.query(Order).count() > 0:
            if os.getenv("AUTO_SOLVE_IF_EMPTY", "1").lower() not in ("0", "false", "no"):
                run_solver(db, fill_geometry=False)
    finally:
        db.close()

    if route_geometry_enabled():

        def _backfill_road_geometry() -> None:
            db2 = SessionLocal()
            try:
                from .api import fill_route_geometries

                missing = (
                    db2.query(Route)
                    .filter((Route.geometry_json.is_(None)) | (Route.geometry_json == ""))
                    .count()
                )
                if missing and db2.query(Route).count() > 0:
                    from .async_util import run_coro_sync

                    run_coro_sync(fill_route_geometries(db2))
            except Exception:
                pass
            finally:
                db2.close()

        threading.Thread(target=_backfill_road_geometry, daemon=True, name="road-geometry").start()

    if YANDEX_MAPS_API_KEY:

        def _regeocode_stale_orders() -> None:
            db3 = SessionLocal()
            try:
                from .async_util import run_coro_sync
                from .models import Order
                from .services.geocode_resolve import apply_geocode_to_orders

                orders = db3.query(Order).filter(Order.geo_source != "yandex").order_by(Order.id).all()
                if orders:
                    run_coro_sync(apply_geocode_to_orders(orders, db=db3))
            except Exception:
                pass
            finally:
                db3.close()

        threading.Thread(target=_regeocode_stale_orders, daemon=True, name="regeocode-orders").start()


@app.get("/api/health")
def health():
    return {"ok": True}
