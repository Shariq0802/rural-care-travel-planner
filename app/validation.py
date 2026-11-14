"""Check and clean the fields an extractor returns.

An extractor (LLM or rules) can return anything. This keeps only values that
look right and turns everything else into None, with a warning.
"""
import re
from datetime import date

FIELDS = ("date", "time", "clinic", "address")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_NULL_WORDS = {"", "null", "none", "n/a", "na", "unknown", "not stated", "not provided"}


def _clean_text(value):
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in _NULL_WORDS:
        return None
    return text


def _words(text):
    """Lower-case, punctuation and line breaks become single spaces."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()


def ground_warnings(fields, source_text):
    """Warn when clinic or address is not written word-for-word in the message.

    A model can mis-copy text (for example a postcode: "FK99 1BC" -> "FK9 91BC").
    Wrong values are then flagged so the person or carer checks them.
    """
    source = _words(source_text)
    warnings = []
    for name in ("clinic", "address"):
        value = fields.get(name)
        if value and _words(value) not in source:
            warnings.append(f"{name} not found word-for-word in the message; please check it")
    return warnings


def validate_fields(raw):
    """Return (fields, warnings). fields always has the 4 keys."""
    warnings = []
    raw = raw if isinstance(raw, dict) else {}
    out = {}

    d = _clean_text(raw.get("date"))
    if d is not None:
        try:
            date.fromisoformat(d)
        except ValueError:
            warnings.append(f"date '{d}' is not a valid YYYY-MM-DD date; ignored")
            d = None
    out["date"] = d

    t = _clean_text(raw.get("time"))
    if t is not None and not _TIME_RE.match(t):
        warnings.append(f"time '{t}' is not HH:MM (24-hour); ignored")
        t = None
    out["time"] = t

    out["clinic"] = _clean_text(raw.get("clinic"))
    out["address"] = _clean_text(raw.get("address"))
    return out, warnings
