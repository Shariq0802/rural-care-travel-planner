"""Journey planning and replanning on the bus timetable.

All times are local times in minutes after midnight. Pure functions on a database
session, so they are easy to test.
"""
import re
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from .db import Place, Stop, StopTime, Trip

BOARD_EARLY_MIN = 5  # be at the stop this many minutes before the bus


def fmt(minutes):
    return f"{(minutes // 60) % 24:02d}:{minutes % 60:02d}"


def _norm(text):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()


def find_place(db: Session, query):
    """Match a clinic name (for example from /extract) to a known place. Longest match wins."""
    q = _norm(query)
    best = None
    for place in db.scalars(select(Place)):
        n = _norm(place.name)
        if n and (n in q or q in n) and (best is None or len(n) > len(_norm(best.name))):
            best = place
    return best


def _options(db: Session, origin_id, dest_id, weekday):
    """All trips that run on `weekday` and go from origin to destination."""
    o, d = aliased(StopTime), aliased(StopTime)
    rows = db.execute(
        select(Trip, o, d)
        .join(o, o.trip_id == Trip.id)
        .join(d, d.trip_id == Trip.id)
        .where(o.stop_id == origin_id, d.stop_id == dest_id, o.seq < d.seq)
    ).all()
    found = []
    for trip, o_st, d_st in rows:
        if weekday in trip.service_days:
            found.append({"trip": trip, "o": o_st, "d": d_st, "dep": o_st.departure_min, "arr": d_st.arrival_min})
    return sorted(found, key=lambda x: x["dep"])


def _build_option(db: Session, raw, delay=0):
    trip, o_st, d_st = raw["trip"], raw["o"], raw["d"]
    stops = []
    rows = db.execute(
        select(StopTime, Stop)
        .join(Stop, Stop.id == StopTime.stop_id)
        .where(StopTime.trip_id == trip.id, StopTime.seq >= o_st.seq, StopTime.seq <= d_st.seq)
        .order_by(StopTime.seq)
    ).all()
    for st, stop in rows:
        stops.append(
            {"stop_id": stop.id, "name": stop.name, "time": fmt(st.arrival_min + delay), "request_stop": stop.request_stop}
        )
    first, last = stops[0], stops[-1]
    dep, arr = raw["dep"] + delay, raw["arr"] + delay

    steps = [f"Be at {first['name']} by {fmt(dep - BOARD_EARLY_MIN)}. The {trip.route} bus to {trip.headsign} leaves at {fmt(dep)}."]
    if first["request_stop"]:
        steps.append("This is a request stop. Signal to the driver so the bus stops.")
    between = len(stops) - 2
    steps.append(
        f"Stay on the bus for {between} more stop{'s' if between != 1 else ''}. The bus may not announce stops; the app will alert you."
    )
    steps.append(f"Get off at {last['name']} at {fmt(arr)}." + (" Tell the driver you want to get off." if last["request_stop"] else ""))

    return {
        "trip_id": trip.id,
        "route": trip.route,
        "headsign": trip.headsign,
        "depart": fmt(dep),
        "arrive": fmt(arr),
        "delay_minutes": delay,
        "stops": stops,
        "steps": steps,
    }


def _response(status, message, option=None, alternatives=None, appointment_min=None, community=False, return_option=None):
    return {
        "return_option": return_option,
        "status": status,
        "message": message,
        "option": option,
        "alternatives": alternatives or [],
        "minutes_before_appointment": (appointment_min - _to_min(option["arrive"])) if option and appointment_min is not None else None,
        "community_transport_suggested": community,
    }


def _to_min(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _names(db, origin_id, dest_id):
    o, d = db.get(Stop, origin_id), db.get(Stop, dest_id)
    return (o.name if o else origin_id), (d.name if d else dest_id)


def plan(db: Session, origin_id, dest_id, appointment: datetime, buffer_min=15, stay_min=60):
    """Find the bus that gets there `buffer_min` minutes before the appointment (latest such bus).

    Earlier buses are returned as safer alternatives. The return bus home is the first bus
    leaving after the appointment plus `stay_min` minutes.
    """
    appt = appointment.hour * 60 + appointment.minute
    options = _options(db, origin_id, dest_id, appointment.weekday())
    ok = [x for x in options if x["arr"] <= appt - buffer_min]
    origin_name, dest_name = _names(db, origin_id, dest_id)
    if not ok:
        return _response(
            "no_bus",
            f"No bus from {origin_name} to {dest_name} gets you there {buffer_min} minutes before your appointment at {fmt(appt)}. "
            "You can request community transport instead.",
            appointment_min=appt,
            community=True,
        )
    best = ok[-1]
    option = _build_option(db, best)
    alternatives = [_build_option(db, x) for x in reversed(ok[:-1])][:2]
    gap = appt - best["arr"]
    message = (
        f"Catch the {option['depart']} bus {option['route']} from {origin_name}. "
        f"You arrive at {dest_name} at {option['arrive']}, {gap} minutes before your appointment at {fmt(appt)}."
    )
    home = [x for x in _options(db, dest_id, origin_id, appointment.weekday()) if x["dep"] >= appt + stay_min]
    return_option = _build_option(db, home[0]) if home else None
    if return_option:
        message += f" To come home, catch the {return_option['depart']} bus {return_option['route']} from {dest_name}; you get back at {return_option['arrive']}."
    else:
        message += f" No bus home after {fmt(appt + stay_min)} today. Request community transport for the return."
    return _response("ok", message, option, alternatives, appt, community=return_option is None, return_option=return_option)


def replan(
    db: Session,
    origin_id,
    dest_id,
    appointment: datetime,
    trip_id=None,
    delay_minutes=0,
    cancelled=False,
    now: datetime | None = None,
    buffer_min=15,
):
    """The planned bus is late or cancelled: keep it, or pick the next one that still works."""
    appt = appointment.hour * 60 + appointment.minute
    now_min = now.hour * 60 + now.minute if now and now.date() == appointment.date() else 0
    origin_name, dest_name = _names(db, origin_id, dest_id)

    candidates = []
    for raw in _options(db, origin_id, dest_id, appointment.weekday()):
        delay = 0
        if raw["trip"].id == trip_id:
            if cancelled:
                continue
            delay = delay_minutes
        if raw["dep"] + delay >= now_min:
            candidates.append((raw, delay))
    candidates.sort(key=lambda c: c[0]["arr"] + c[1])

    # 1. The affected bus is only late and you still arrive in time: keep it.
    for raw, delay in candidates:
        if raw["trip"].id == trip_id and not cancelled and raw["arr"] + delay <= appt - buffer_min:
            option = _build_option(db, raw, delay)
            gap = appt - (raw["arr"] + delay)
            return _response(
                "on_time",
                f"Your bus is {delay} minutes late, but you still arrive at {option['arrive']}, {gap} minutes before your appointment. Keep your plan.",
                option,
                appointment_min=appt,
            )

    # 2. Best other bus: arrives with the full buffer, else at least before the appointment.
    for need, status in ((appt - buffer_min, "replanned"), (appt, "tight")):
        for raw, delay in candidates:
            if raw["arr"] + delay <= need:
                option = _build_option(db, raw, delay)
                gap = appt - (raw["arr"] + delay)
                what = "cancelled" if cancelled else f"{delay} minutes late"
                tail = "" if status == "replanned" else " This is tight, so tell the clinic you may arrive close to your time."
                return _response(
                    status,
                    f"Your bus is {what}. New plan: catch the {option['depart']} bus {option['route']} from {origin_name}. "
                    f"You arrive at {dest_name} at {option['arrive']}, {gap} minutes before your appointment.{tail}",
                    option,
                    appointment_min=appt,
                )

    # 3. Nothing arrives in time.
    fallback = _build_option(db, candidates[0][0], candidates[0][1]) if candidates else None
    late_by = (_to_min(fallback["arrive"]) - appt) if fallback else None
    message = "No bus gets you to your appointment on time. "
    if fallback:
        message += f"The next bus arrives at {fallback['arrive']}, {late_by} minutes after your appointment. "
    message += "Request community transport and ask the clinic if they can move your appointment."
    return _response("late", message, fallback, appointment_min=appt, community=True)
