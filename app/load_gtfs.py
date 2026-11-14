"""Load a GTFS folder (stops, routes, calendar, trips, stop_times, places) into the database.

Run:  python -m app.load_gtfs data/gtfs_sample
Loading again replaces the old timetable.
"""
import csv
import sys
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .db import Place, SessionLocal, Stop, StopTime, Trip, init_db

DEFAULT_DIR = Path(__file__).resolve().parent.parent / "data" / "gtfs_sample"
_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _rows(folder, name):
    path = Path(folder) / name
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _minutes(hhmmss):
    h, m, *_ = hhmmss.split(":")
    return int(h) * 60 + int(m)  # GTFS allows hours above 23 for trips after midnight


def load_gtfs(db: Session, folder=DEFAULT_DIR):
    """Replace the timetable with the GTFS files in `folder`. Returns counts."""
    for model in (StopTime, Place, Trip, Stop):
        db.execute(delete(model))

    routes = {r["route_id"]: r for r in _rows(folder, "routes.txt")}
    services = {
        c["service_id"]: [i for i, d in enumerate(_DAYS) if c[d] == "1"] for c in _rows(folder, "calendar.txt")
    }

    for s in _rows(folder, "stops.txt"):
        db.add(
            Stop(
                id=s["stop_id"],
                name=s["stop_name"],
                lat=float(s["stop_lat"]),
                lon=float(s["stop_lon"]),
                request_stop=s.get("request_stop", "0") == "1",
            )
        )
    for t in _rows(folder, "trips.txt"):
        db.add(
            Trip(
                id=t["trip_id"],
                route=routes[t["route_id"]]["route_short_name"],
                headsign=t["trip_headsign"],
                direction=int(t.get("direction_id") or 0),
                service_days=services.get(t["service_id"], []),
            )
        )
    db.flush()
    for st in _rows(folder, "stop_times.txt"):
        db.add(
            StopTime(
                trip_id=st["trip_id"],
                stop_id=st["stop_id"],
                seq=int(st["stop_sequence"]),
                arrival_min=_minutes(st["arrival_time"]),
                departure_min=_minutes(st["departure_time"]),
            )
        )
    for p in _rows(folder, "places.txt"):
        db.add(Place(name=p["name"], address=p["address"], stop_id=p["stop_id"]))
    db.commit()
    return {
        "stops": db.scalar(select(func.count()).select_from(Stop)),
        "trips": db.scalar(select(func.count()).select_from(Trip)),
        "stop_times": db.scalar(select(func.count()).select_from(StopTime)),
        "places": db.scalar(select(func.count()).select_from(Place)),
    }


if __name__ == "__main__":
    init_db()
    folder = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DIR
    with SessionLocal() as session:
        print("loaded", load_gtfs(session, folder))
