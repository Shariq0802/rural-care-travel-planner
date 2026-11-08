from contextlib import asynccontextmanager
from datetime import date, datetime, timezone

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from . import config
from .db import Extraction, get_db, init_db
from .extractor_baseline import extract_baseline
from .extractor_llm import LLMError, extract_llm
from .schemas import ConfirmResponse, ExtractRequest, ExtractResponse, Fields
from .validation import validate_fields


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
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
