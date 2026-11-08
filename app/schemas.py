from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class ExtractRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000, description="Appointment letter or SMS text")
    reference_date: Optional[date] = Field(
        default=None, description="Date the message was received. Defaults to today."
    )


class Fields(BaseModel):
    date: Optional[str] = Field(default=None, description="YYYY-MM-DD")
    time: Optional[str] = Field(default=None, description="HH:MM, 24-hour")
    clinic: Optional[str] = None
    address: Optional[str] = None


class ExtractResponse(Fields):
    id: str
    backend: str
    model: str
    prompt_version: str
    warnings: list[str] = []
    # Always true: a person (or carer) must check the details before they are used.
    needs_confirmation: bool = True


class ConfirmResponse(BaseModel):
    id: str
    confirmed: Fields
    confirmed_at: datetime
