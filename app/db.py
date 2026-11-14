from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from . import config


class Base(DeclarativeBase):
    pass


class Extraction(Base):
    """One extraction result.

    Privacy: the original letter/SMS text is NOT stored, only the extracted fields.
    """

    __tablename__ = "extractions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    backend: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(80))
    prompt_version: Mapped[str] = mapped_column(String(10))
    extracted: Mapped[dict] = mapped_column(JSON)
    confirmed: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Stop(Base):
    __tablename__ = "stops"

    id: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    # Rural request stop: the passenger must signal the driver or the bus will not stop.
    request_stop: Mapped[bool] = mapped_column(Boolean, default=False)


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    route: Mapped[str] = mapped_column(String(20))
    headsign: Mapped[str] = mapped_column(String(120))
    direction: Mapped[int] = mapped_column(Integer, default=0)
    service_days: Mapped[list] = mapped_column(JSON)  # weekday numbers, Monday = 0


class StopTime(Base):
    __tablename__ = "stop_times"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id"), index=True)
    stop_id: Mapped[str] = mapped_column(ForeignKey("stops.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    arrival_min: Mapped[int] = mapped_column(Integer)  # minutes after midnight
    departure_min: Mapped[int] = mapped_column(Integer)


class Place(Base):
    """A clinic or other place, and the bus stop nearest to it."""

    __tablename__ = "places"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(160))
    address: Mapped[str] = mapped_column(String(240))
    stop_id: Mapped[str] = mapped_column(ForeignKey("stops.id"))


engine = create_engine(config.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db():
    Base.metadata.create_all(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
