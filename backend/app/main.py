import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import router, run_solver
from .config import CORS_ORIGINS, EXCEL_PATH
from .database import Base, SessionLocal, engine
from .migrate import ensure_schema
from .models import Order
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
                run_solver(db)
    finally:
        db.close()


@app.get("/api/health")
def health():
    return {"ok": True}
