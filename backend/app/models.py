from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(160), default="")
    phone: Mapped[str] = mapped_column(String(32), default="", index=True)
    role: Mapped[str] = mapped_column(String(20), default="driver")  # dispatcher|driver
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_geo_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    geo_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    shift_status: Mapped[str] = mapped_column(String(24), default="waiting")
    shift_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    shift_ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(80))
    plate: Mapped[str] = mapped_column(String(20), unique=True)
    capacity_kg: Mapped[int] = mapped_column(Integer)
    max_mass_kg: Mapped[int] = mapped_column(Integer)
    height_m: Mapped[float] = mapped_column(Float)
    width_m: Mapped[float] = mapped_column(Float)
    length_m: Mapped[float] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    color: Mapped[str] = mapped_column(String(16), default="#0F6B8F")
    note: Mapped[str] = mapped_column(String(255), default="")

    routes = relationship("Route", back_populates="vehicle")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(300))
    address: Mapped[str] = mapped_column(String(300))
    weight_kg: Mapped[int] = mapped_column(Integer)
    preferred_time: Mapped[str | None] = mapped_column(String(16), nullable=True)
    window_start: Mapped[str | None] = mapped_column(String(8), nullable=True)
    window_end: Mapped[str | None] = mapped_column(String(8), nullable=True)
    unload_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    geo_source: Mapped[str] = mapped_column(String(32), default="auto")
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    import_batch: Mapped[str] = mapped_column(String(40), default="")
    warning: Mapped[str] = mapped_column(Text, default="")
    restricted_historic: Mapped[bool] = mapped_column(Boolean, default=False)
    contact_phone: Mapped[str] = mapped_column(String(40), default="")
    dispatcher_note: Mapped[str] = mapped_column(Text, default="")


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"))
    status: Mapped[str] = mapped_column(String(20), default="planned")
    load_kg: Mapped[int] = mapped_column(Integer, default=0)
    distance_m: Mapped[int] = mapped_column(Integer, default=0)
    duration_s: Mapped[int] = mapped_column(Integer, default=0)
    finish_time: Mapped[str] = mapped_column(String(8), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    warning: Mapped[str] = mapped_column(Text, default="")
    geometry_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    vehicle = relationship("Vehicle", back_populates="routes")
    stops = relationship("RouteStop", back_populates="route", cascade="all, delete-orphan", order_by="RouteStop.seq")


class RouteStop(Base):
    __tablename__ = "route_stops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id"))
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    seq: Mapped[int] = mapped_column(Integer)
    eta: Mapped[str] = mapped_column(String(8), default="")
    distance_from_prev_m: Mapped[int] = mapped_column(Integer, default=0)
    travel_s: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|enroute|at_stop|unloading|done|problem
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    unloading_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    actual_weight_kg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    driver_comment: Mapped[str] = mapped_column(Text, default="")
    event_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    event_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    problem_reason: Mapped[str] = mapped_column(String(160), default="")
    problem_text: Mapped[str] = mapped_column(Text, default="")
    dispatcher_reply: Mapped[str] = mapped_column(Text, default="")

    route = relationship("Route", back_populates="stops")
    order = relationship("Order")


class DriverMessage(Base):
    __tablename__ = "driver_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    to_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    stop_id: Mapped[int | None] = mapped_column(ForeignKey("route_stops.id"), nullable=True)
    text: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[str] = mapped_column(String(24), default="chat")  # chat|problem
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DriverNotification(Base):
    __tablename__ = "driver_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    key: Mapped[str] = mapped_column(String(120), default="", index=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[str] = mapped_column(String(40), default="info")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    read: Mapped[bool] = mapped_column(Boolean, default=False)


class TripArchive(Base):
    __tablename__ = "trip_archive"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    driver_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    plate: Mapped[str] = mapped_column(String(20), default="")
    route_date: Mapped[str] = mapped_column(String(16), default="")
    orders_n: Mapped[int] = mapped_column(Integer, default=0)
    done_n: Mapped[int] = mapped_column(Integer, default=0)
    problem_n: Mapped[int] = mapped_column(Integer, default=0)
    weight_kg: Mapped[int] = mapped_column(Integer, default=0)
    distance_m: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[str] = mapped_column(String(32), default="")
    finished_at: Mapped[str] = mapped_column(String(32), default="")
    detail_json: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Unassigned(Base):
    __tablename__ = "unassigned"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    reason: Mapped[str] = mapped_column(Text)
    conflicts: Mapped[str] = mapped_column(Text, default="")
    suggestions: Mapped[str] = mapped_column(Text, default="")


class RoadRestriction(Base):
    __tablename__ = "road_restrictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    street_pattern: Mapped[str] = mapped_column(String(200))
    max_capacity_kg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_mass_kg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_height_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_width_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_length_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id"), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
