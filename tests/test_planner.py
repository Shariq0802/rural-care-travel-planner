from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import planner
from app.db import Base, get_db
from app.load_gtfs import load_gtfs
from app.main import app

HOME, HOSP = "GLN_HALL", "DUN_HOSP"
TUE_11 = datetime(2026, 11, 24, 11, 0)  # Tuesday, appointment at 11:00
SUN_11 = datetime(2026, 11, 22, 11, 0)  # Sunday: no buses


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    counts = load_gtfs(session)
    assert counts == {"stops": 6, "trips": 14, "stop_times": 84, "places": 3}
    yield session
    session.close()


def test_load_is_repeatable(db):
    assert load_gtfs(db)["trips"] == 14  # loading again replaces, no duplicates


def test_plan_picks_latest_bus_that_arrives_in_time(db):
    r = planner.plan(db, HOME, HOSP, TUE_11)
    assert r["status"] == "ok"
    assert r["option"]["depart"] == "09:40" and r["option"]["arrive"] == "10:30"
    assert r["minutes_before_appointment"] == 30
    assert [a["depart"] for a in r["alternatives"]] == ["07:10"]  # the safer, earlier bus
    assert "09:40" in r["message"]


def test_plan_steps_mention_request_stop_and_get_off(db):
    steps = planner.plan(db, HOME, HOSP, TUE_11)["option"]["steps"]
    assert any("request stop" in s.lower() and "signal" in s.lower() for s in steps)
    assert any("Get off at Dunmore Community Hospital" in s for s in steps)
    stops = planner.plan(db, HOME, HOSP, TUE_11)["option"]["stops"]
    assert [x["stop_id"] for x in stops][0] == HOME and [x["stop_id"] for x in stops][-1] == HOSP


def test_plan_includes_bus_home(db):
    r = planner.plan(db, HOME, HOSP, TUE_11, stay_min=60)
    assert r["return_option"]["depart"] == "13:40" and r["return_option"]["arrive"] == "14:30"
    assert r["return_option"]["headsign"] == "Glenarran"
    assert r["community_transport_suggested"] is False


def test_plan_no_bus_home_late_in_the_day(db):
    r = planner.plan(db, HOME, HOSP, datetime(2026, 11, 24, 17, 0), stay_min=60)  # last bus home is 18:30
    assert r["return_option"]["depart"] == "18:30"
    r = planner.plan(db, HOME, HOSP, datetime(2026, 11, 24, 17, 45), stay_min=60)  # needs a bus after 18:45
    assert r["status"] == "ok" and r["return_option"] is None and r["community_transport_suggested"] is True


def test_plan_no_bus(db):
    for when in (SUN_11, datetime(2026, 11, 24, 7, 30)):  # Sunday; too early in the morning
        r = planner.plan(db, HOME, HOSP, when)
        assert r["status"] == "no_bus" and r["community_transport_suggested"] is True and r["option"] is None


def test_replan_small_delay_keeps_the_bus(db):
    trip = planner.plan(db, HOME, HOSP, TUE_11)["option"]["trip_id"]
    r = planner.replan(db, HOME, HOSP, TUE_11, trip_id=trip, delay_minutes=5, now=datetime(2026, 11, 24, 8, 0))
    assert r["status"] == "on_time" and r["option"]["arrive"] == "10:35" and r["option"]["delay_minutes"] == 5


def test_replan_big_delay_is_tight(db):
    trip = planner.plan(db, HOME, HOSP, TUE_11)["option"]["trip_id"]
    r = planner.replan(db, HOME, HOSP, TUE_11, trip_id=trip, delay_minutes=20, now=datetime(2026, 11, 24, 8, 0))
    assert r["status"] == "tight" and r["option"]["arrive"] == "10:50" and "tell the clinic" in r["message"]


def test_replan_cancelled_bus_means_late_and_community_transport(db):
    trip = planner.plan(db, HOME, HOSP, TUE_11)["option"]["trip_id"]
    r = planner.replan(db, HOME, HOSP, TUE_11, trip_id=trip, cancelled=True, now=datetime(2026, 11, 24, 8, 0))
    assert r["status"] == "late" and r["community_transport_suggested"] is True
    assert r["option"]["depart"] == "12:15" and "125 minutes after" in r["message"]


def test_replan_cancelled_bus_with_an_earlier_bus_still_available(db):
    # Appointment 17:00: the 12:15 bus arrives 13:05, so there is another option after the 15:30 one is cancelled.
    appt = datetime(2026, 11, 24, 17, 0)
    first = planner.plan(db, HOME, HOSP, appt)["option"]
    assert first["depart"] == "15:30"
    r = planner.replan(db, HOME, HOSP, appt, trip_id=first["trip_id"], cancelled=True, now=datetime(2026, 11, 24, 12, 0))
    assert r["status"] == "replanned" and r["option"]["depart"] == "12:15"


def test_replan_ignores_buses_already_gone(db):
    trip = planner.plan(db, HOME, HOSP, TUE_11)["option"]["trip_id"]
    r = planner.replan(db, HOME, HOSP, TUE_11, trip_id=trip, cancelled=True, now=datetime(2026, 11, 24, 9, 0))
    assert r["option"]["depart"] != "07:10"  # the 07:10 bus left two hours ago


def test_find_place(db):
    assert planner.find_place(db, "Dunmore Community Hospital").stop_id == HOSP
    assert planner.find_place(db, "dunmore community hospital, harbour road").stop_id == HOSP
    assert planner.find_place(db, "Somewhere Else Surgery") is None


# ---- through the API ------------------------------------------------------------------


@pytest.fixture()
def client(db):
    def override():
        yield db

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_api_plan_with_clinic_name(client):
    r = client.post(
        "/plan",
        json={"origin_stop_id": HOME, "clinic_name": "Dunmore Community Hospital", "appointment": "2026-11-24T11:00"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["option"]["depart"] == "09:40" and body["return_option"]["depart"] == "13:40"


def test_api_replan(client):
    plan = client.post("/plan", json={"origin_stop_id": HOME, "destination_stop_id": HOSP, "appointment": "2026-11-24T11:00"}).json()
    r = client.post(
        "/replan",
        json={
            "origin_stop_id": HOME,
            "destination_stop_id": HOSP,
            "appointment": "2026-11-24T11:00",
            "trip_id": plan["option"]["trip_id"],
            "cancelled": True,
            "now": "2026-11-24T08:00",
        },
    )
    assert r.status_code == 200 and r.json()["status"] == "late"


def test_api_errors(client):
    ok = {"origin_stop_id": HOME, "destination_stop_id": HOSP, "appointment": "2026-11-24T11:00"}
    assert client.post("/plan", json={**ok, "origin_stop_id": "NOPE"}).status_code == 404
    assert client.post("/plan", json={**ok, "destination_stop_id": "NOPE"}).status_code == 404
    assert client.post("/plan", json={**ok, "destination_stop_id": None, "clinic_name": "Unknown Clinic"}).status_code == 404
    assert client.post("/plan", json={**ok, "destination_stop_id": None}).status_code == 422
    assert client.post("/plan", json={**ok, "appointment": "not a date"}).status_code == 422


def test_api_stops_and_places(client):
    stops = client.get("/stops").json()
    assert len(stops) == 6 and {"stop_id", "name", "lat", "lon", "request_stop"} <= set(stops[0])
    assert len(client.get("/places").json()) == 3
    assert client.get("/places", params={"q": "Dunmore Community Hospital"}).json()[0]["stop_id"] == HOSP
    assert client.get("/places", params={"q": "nothing"}).json() == []
