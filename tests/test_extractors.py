import json
from datetime import date

import httpx
import pytest

from app.extractor_baseline import extract_baseline
from app.extractor_llm import LLMError, extract_llm
from app.prompts import build_messages
from app.validation import validate_fields
from eval.scoring import score_one, text_match

REF = date(2026, 11, 2)


def _client(content=None, status=200):
    """A fake Ollama server."""

    def handler(request):
        body = json.loads(request.content)
        assert body["model"]
        assert body["format"]["required"] == ["date", "time", "clinic", "address"]
        assert body["options"]["temperature"] == 0
        if status != 200:
            return httpx.Response(status)
        return httpx.Response(200, json={"message": {"role": "assistant", "content": content}})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_llm_happy_path():
    answer = {"date": "2026-11-24", "time": "10:30", "clinic": "Dunmore Community Hospital", "address": "Harbour Road"}
    fields, warnings = extract_llm("x", REF, client=_client(json.dumps(answer)))
    assert fields == answer and warnings == []


def test_llm_bad_values_become_null_with_warning():
    answer = {"date": "24/11/2026", "time": "10.30am", "clinic": "N/A", "address": ""}
    fields, warnings = extract_llm("x", REF, client=_client(json.dumps(answer)))
    assert fields == {"date": None, "time": None, "clinic": None, "address": None}
    assert len(warnings) == 2


def test_llm_json_inside_text_is_recovered():
    content = 'Sure! {"date": null, "time": "09:00", "clinic": null, "address": null} Hope that helps.'
    fields, _ = extract_llm("x", REF, client=_client(content))
    assert fields["time"] == "09:00"


def test_llm_garbage_raises():
    with pytest.raises(LLMError):
        extract_llm("x", REF, client=_client("no json here"))


def test_llm_server_error_raises():
    with pytest.raises(LLMError):
        extract_llm("x", REF, client=_client(status=500))


def test_ground_warnings():
    from app.validation import ground_warnings

    source = "APPT 11 DEC. MILLBANK HEALTH CENTRE, 3 CROFT ROAD, MILLBANK, FK99 1BC."
    ok = {"clinic": "Millbank Health Centre", "address": "3 Croft Road, Millbank, FK99 1BC"}
    assert ground_warnings(ok, source) == []
    bad = {"clinic": "Millbank Health Centre", "address": "3 Croft Road, Millbank, FK9 91BC"}  # mis-copied postcode
    assert len(ground_warnings(bad, source)) == 1
    multi = "Pier Street\nCorrieden\nPA99 9QR"
    assert ground_warnings({"address": "Pier Street, Corrieden, PA99 9QR"}, multi) == []
    assert ground_warnings({"clinic": None, "address": None}, source) == []


def test_prompt_versions():
    assert len(build_messages("t", REF, "v1")) == 2
    assert len(build_messages("t", REF, "v2")) == 2 + 3 * 2
    assert len(build_messages("t", REF, "v3")) == 2 + 5 * 2
    with pytest.raises(ValueError):
        build_messages("t", REF, "v9")


def test_validation_rejects_impossible_date():
    fields, warnings = validate_fields({"date": "2026-02-30", "time": "25:00"})
    assert fields["date"] is None and fields["time"] is None and len(warnings) == 2


def test_baseline_basic():
    text = "Appointment on 3 December 2026 at 09:15. Strathmore Health Centre, Bridge Street, Strathmore, DD99 4EF."
    fields, _ = extract_baseline(text, REF)
    assert fields["date"] == "2026-12-03" and fields["time"] == "09:15"
    assert "Strathmore Health Centre" in fields["clinic"]


def test_scoring():
    assert text_match("Mill Road Surgery", "mill road surgery!")
    assert text_match("Harbour Road, Dunmore", "Dunmore Hospital, Harbour Road, Dunmore")
    assert not text_match("Mill Road Surgery", "Elm Surgery")
    assert text_match(None, None) and not text_match(None, "x") and not text_match("x", None)
    expected = {"date": "2026-11-24", "time": None, "clinic": "A B", "address": None}
    predicted = {"date": "2026-11-24", "time": "10:00", "clinic": "A B", "address": None}
    assert score_one(expected, predicted) == {"date": True, "time": False, "clinic": True, "address": True}
