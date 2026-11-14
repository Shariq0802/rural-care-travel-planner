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


# ---- journey planning ----------------------------------------------------------------


class PlanRequest(BaseModel):
    origin_stop_id: str = Field(description="Stop the person starts from, see GET /stops")
    destination_stop_id: Optional[str] = Field(default=None, description="Give this OR clinic_name")
    clinic_name: Optional[str] = Field(default=None, description="For example the clinic from /extract")
    appointment: datetime = Field(description="Local date and time of the appointment, e.g. 2026-11-24T11:00")
    buffer_minutes: int = Field(default=15, ge=0, le=120, description="Arrive this long before the appointment")
    stay_minutes: int = Field(default=60, ge=0, le=480, description="How long you expect to stay, to find the bus home")


class ReplanRequest(PlanRequest):
    trip_id: Optional[str] = Field(default=None, description="The bus that is late or cancelled")
    delay_minutes: int = Field(default=0, ge=0, le=240)
    cancelled: bool = False
    now: Optional[datetime] = Field(default=None, description="Current local time. Buses before this are ignored.")


class StopOut(BaseModel):
    stop_id: str
    name: str
    time: str
    request_stop: bool


class OptionOut(BaseModel):
    trip_id: str
    route: str
    headsign: str
    depart: str
    arrive: str
    delay_minutes: int
    stops: list[StopOut]
    steps: list[str]


class PlanResponse(BaseModel):
    status: str  # plan: ok | no_bus. replan: on_time | replanned | tight | late
    message: str  # short sentence that can be read out loud
    option: Optional[OptionOut] = None
    return_option: Optional[OptionOut] = None  # the bus home (only from /plan)
    alternatives: list[OptionOut] = []
    minutes_before_appointment: Optional[int] = None
    community_transport_suggested: bool = False


class StopInfo(BaseModel):
    stop_id: str
    name: str
    lat: float
    lon: float
    request_stop: bool


class PlaceInfo(BaseModel):
    name: str
    address: str
    stop_id: str
