"""A deliberately simple rule-based extractor (regular expressions).

It exists only as a comparison point: the LLM should clearly beat it.
It takes the FIRST date, FIRST time, FIRST clinic-like name and FIRST postcode
it finds, and handles no spoken numbers like "half past two".
"""
import re
from datetime import date, timedelta

from .validation import validate_fields

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_DATE_TEXT = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?(?:\s+of)?\s+"
    r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|"
    r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b(?:,?\s+(\d{4}))?",
    re.I,
)
_DATE_NUM = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_TIME_COLON = re.compile(r"(?<![\d/])(\d{1,2})[:.](\d{2})\s*(am|pm)?(?!\d)", re.I)
_TIME_HOUR = re.compile(r"\b(\d{1,2})\s*(am|pm)\b", re.I)
_CLINIC = re.compile(
    r"\b((?:[A-Z][A-Za-z'-]*\s+){1,4}"
    r"(?:Hospital|Health Centre|Medical Centre|Medical Practice|Surgery|Dental Practice|Dental Care|"
    r"Village Hall|Clinic|Unit|Physio))\b"
)
_POSTCODE = re.compile(r"\b[A-Z]{1,2}\d{1,2}[A-Z]?\s?\d[A-Z]{2}\b", re.I)
_SPLITTERS = (". ", ": ", "\n\n", " - ", "(", ")")


def _find_date(text, ref):
    candidates = []
    for m in _DATE_NUM.finditer(text):
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        candidates.append((m.start(), day, month, year))
    for m in _DATE_TEXT.finditer(text):
        day = int(m.group(1))
        month = _MONTHS[m.group(2)[:3].lower()]
        year = int(m.group(3)) if m.group(3) else None
        candidates.append((m.start(), day, month, year))
    for _, day, month, year in sorted(candidates):
        try:
            if year is None:
                year = ref.year
                if date(year, month, day) < ref:
                    year += 1
            return date(year, month, day).isoformat()
        except ValueError:
            continue
    if re.search(r"\btomorrow\b", text, re.I):
        return (ref + timedelta(days=1)).isoformat()
    return None


def _to_24h(hour, minute, meridiem):
    if meridiem:
        hour = hour % 12 + (12 if meridiem.lower() == "pm" else 0)
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def _find_time(text):
    candidates = []
    for m in _TIME_COLON.finditer(text):
        candidates.append((m.start(), int(m.group(1)), int(m.group(2)), m.group(3)))
    for m in _TIME_HOUR.finditer(text):
        candidates.append((m.start(), int(m.group(1)), 0, m.group(2)))
    for _, hour, minute, meridiem in sorted(candidates, key=lambda c: c[0]):
        value = _to_24h(hour, minute, meridiem)
        if value:
            return value
    return None


def _find_address(text):
    m = _POSTCODE.search(text)
    if not m:
        return None
    before = text[max(0, m.start() - 80) : m.start()]
    cut = max(before.rfind(s) + len(s) if before.rfind(s) != -1 else 0 for s in _SPLITTERS)
    address = (before[cut:] + m.group(0)).replace("\n", ", ")
    return re.sub(r",\s*,", ",", address).strip(" ,")


def extract_baseline(text, reference_date=None):
    reference_date = reference_date or date.today()
    clinic = _CLINIC.search(text)
    raw = {
        "date": _find_date(text, reference_date),
        "time": _find_time(text),
        "clinic": re.sub(r"\s+", " ", clinic.group(1)) if clinic else None,
        "address": _find_address(text),
    }
    return validate_fields(raw)
