from contextlib import asynccontextmanager
from datetime import date, datetime, timezone

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import config
from . import planner
from .db import Extraction, Place, SessionLocal, Stop, get_db, init_db
from .load_gtfs import load_gtfs
from .extractor_baseline import extract_baseline
from .extractor_llm import LLMError, extract_llm
from .schemas import (
    ConfirmResponse,
    ExtractRequest,
    ExtractResponse,
    Fields,
    PlaceInfo,
    PlanRequest,
    PlanResponse,
    ReplanRequest,
    StopInfo,
)
from .validation import ground_warnings, validate_fields


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with SessionLocal() as db:  # first start: load the sample timetable
        if db.scalar(select(func.count()).select_from(Stop)) == 0:
            load_gtfs(db)
    yield


app = FastAPI(title="Rural Care Travel Planner API", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "extractor": config.EXTRACTOR}


@app.post("/extract", response_model=ExtractResponse)
def extract(body: ExtractRequest, db: Session = Depends(get_db)):
    """Read an appointment letter/SMS and return date, time, clinic and address.

    The result is a DRAFT: show it to the user or carer to confirm (see /extract/{id}/confirm).
    """
    reference_date = body.reference_date or date.today()

    if config.EXTRACTOR == "baseline":
        fields, warnings = extract_baseline(body.text, reference_date)
        backend, model, prompt_version = "baseline", "regex", "-"
    else:
        try:
            fields, warnings = extract_llm(body.text, reference_date)
        except LLMError as exc:
            raise HTTPException(status_code=502, detail=str(exc))
        backend, model, prompt_version = "llm", config.OLLAMA_MODEL, config.PROMPT_VERSION

    warnings = warnings + ground_warnings(fields, body.text)

    row = Extraction(backend=backend, model=model, prompt_version=prompt_version, extracted=fields)
    db.add(row)
    db.commit()

    return ExtractResponse(
        id=row.id, backend=backend, model=model, prompt_version=prompt_version, warnings=warnings, **fields
    )


@app.post("/extract/{extraction_id}/confirm", response_model=ConfirmResponse)
def confirm(extraction_id: str, body: Fields, db: Session = Depends(get_db)):
    """The user or carer confirms (or corrects) the extracted details."""
    row = db.get(Extraction, extraction_id)
    if row is None:
        raise HTTPException(status_code=404, detail="extraction not found")
    fields, warnings = validate_fields(body.model_dump())
    if warnings:
        raise HTTPException(status_code=422, detail=warnings)
    row.confirmed = fields
    row.confirmed_at = datetime.now(timezone.utc)
    db.commit()
    return ConfirmResponse(id=row.id, confirmed=Fields(**fields), confirmed_at=row.confirmed_at)


# ---- journey planning ----------------------------------------------------------------


def _resolve_destination(db: Session, body: PlanRequest):
    if body.destination_stop_id:
        if db.get(Stop, body.destination_stop_id) is None:
            raise HTTPException(status_code=404, detail="destination stop not found")
        return body.destination_stop_id
    if body.clinic_name:
        place = planner.find_place(db, body.clinic_name)
        if place is None:
            raise HTTPException(status_code=404, detail=f"no known place matches '{body.clinic_name}'")
        return place.stop_id
    raise HTTPException(status_code=422, detail="give destination_stop_id or clinic_name")


def _check_origin(db: Session, stop_id: str):
    if db.get(Stop, stop_id) is None:
        raise HTTPException(status_code=404, detail="origin stop not found")


@app.get("/stops", response_model=list[StopInfo])
def stops(db: Session = Depends(get_db)):
    rows = db.scalars(select(Stop).order_by(Stop.name))
    return [StopInfo(stop_id=s.id, name=s.name, lat=s.lat, lon=s.lon, request_stop=s.request_stop) for s in rows]


@app.get("/places", response_model=list[PlaceInfo])
def places(q: str | None = None, db: Session = Depends(get_db)):
    """Known clinics and the bus stop next to each. With q, only the best match."""
    if q:
        match = planner.find_place(db, q)
        rows = [match] if match else []
    else:
        rows = list(db.scalars(select(Place).order_by(Place.name)))
    return [PlaceInfo(name=p.name, address=p.address, stop_id=p.stop_id) for p in rows]


@app.post("/plan", response_model=PlanResponse)
def plan(body: PlanRequest, db: Session = Depends(get_db)):
    """Bus journey that arrives before the appointment, plus safer earlier alternatives."""
    _check_origin(db, body.origin_stop_id)
    dest = _resolve_destination(db, body)
    return planner.plan(db, body.origin_stop_id, dest, body.appointment, body.buffer_minutes, body.stay_minutes)


@app.post("/replan", response_model=PlanResponse)
def replan(body: ReplanRequest, db: Session = Depends(get_db)):
    """The planned bus is late or cancelled: keep it, pick the next bus, or suggest community transport."""
    _check_origin(db, body.origin_stop_id)
    dest = _resolve_destination(db, body)
    return planner.replan(
        db,
        body.origin_stop_id,
        dest,
        body.appointment,
        trip_id=body.trip_id,
        delay_minutes=body.delay_minutes,
        cancelled=body.cancelled,
        now=body.now,
        buffer_min=body.buffer_minutes,
    )
