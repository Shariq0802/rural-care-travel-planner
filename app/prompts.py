"""Prompts for the appointment extractor.

v1: plain instructions (zero-shot).
v2: same instructions + 3 worked examples. The examples are NOT taken from
    data/letters.json, so the test set stays unseen.
"""
import json

SYSTEM_V1 = """You extract appointment details from a UK health appointment letter or text message.

Return ONLY a JSON object with exactly these keys: date, time, clinic, address.

Rules:
- date: the date of the appointment itself, as YYYY-MM-DD.
  Ignore the date of the letter and any past dates.
  If the appointment was changed or rebooked, use the NEW date.
  If the year is missing, use the year that gives the next upcoming date after the reference date.
  Words like "tomorrow" are relative to the reference date.
  If there is no single exact date (for example only a week or month is given), use null.
- time: the start time in 24-hour HH:MM format. If there is no exact time, use null.
- clinic: the name of the place where the appointment happens (hospital, health centre, surgery, clinic, hall, unit). Use null if not stated.
- address: the street address of that place, including the postcode, as written in the message. Use null if not stated.
- Never guess. If a value is not clearly stated, use null."""

_EXAMPLES = [
    (
        "2026-10-05",
        "Notice of change: your appointment at Kirkmoor Hospital, Low Road, Kirkmoor, XX1 2YY on 12 October at 09:00 "
        "is cancelled. New appointment: Friday 16 October at 13:45.",
        {
            "date": "2026-10-16",
            "time": "13:45",
            "clinic": "Kirkmoor Hospital",
            "address": "Low Road, Kirkmoor, XX1 2YY",
        },
    ),
    (
        "2026-10-14",
        "Heathfield Surgery, 1 The Green, Heathfield, XX3 4ZZ. You are due a review in early November. "
        "We will text you the exact date and time.",
        {
            "date": None,
            "time": None,
            "clinic": "Heathfield Surgery",
            "address": "1 The Green, Heathfield, XX3 4ZZ",
        },
    ),
    (
        "2026-10-20",
        "Your clinic visit is on the 5th of November at twenty to nine in the morning at Pinewood Medical Centre.",
        {"date": "2026-11-05", "time": "08:40", "clinic": "Pinewood Medical Centre", "address": None},
    ),
]

SCHEMA = {
    "type": "object",
    "properties": {
        "date": {"type": ["string", "null"]},
        "time": {"type": ["string", "null"]},
        "clinic": {"type": ["string", "null"]},
        "address": {"type": ["string", "null"]},
    },
    "required": ["date", "time", "clinic", "address"],
}


def user_message(text, reference_date):
    return (
        f"Reference date (when the message was received): {reference_date.isoformat()} "
        f"({reference_date.strftime('%A')})\n\nMessage:\n\"\"\"\n{text}\n\"\"\""
    )


def build_messages(text, reference_date, version="v1"):
    from datetime import date

    messages = [{"role": "system", "content": SYSTEM_V1}]
    if version == "v2":
        for ref, example_text, answer in _EXAMPLES:
            messages.append({"role": "user", "content": user_message(example_text, date.fromisoformat(ref))})
            messages.append({"role": "assistant", "content": json.dumps(answer)})
    elif version != "v1":
        raise ValueError(f"unknown prompt version: {version}")
    messages.append({"role": "user", "content": user_message(text, reference_date)})
    return messages
