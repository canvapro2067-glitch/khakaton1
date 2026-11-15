import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / ".env.txt")

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'moloko.db'}")
SECRET_KEY = os.getenv("SECRET_KEY", "moloko-mir-grodno-hackathon-secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7
YANDEX_MAPS_API_KEY = os.getenv("YANDEX_MAPS_API_KEY", "")
YANDEX_ROUTING_API_KEY = os.getenv("YANDEX_ROUTING_API_KEY", "")
EXCEL_PATH = ROOT / "data.xlsx"
CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


def route_geometry_enabled() -> bool:
    return os.getenv("SKIP_ROUTE_GEOMETRY", "").lower() not in ("1", "true", "yes")
