import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import config, extractor_llm
from app.db import Base, Extraction, get_db
from app.main import app


@pytest.fixture()
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    client = TestClient(app)
    client.session_factory = Session
    yield client
    app.dependency_overrides.clear()


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_extract_baseline_and_confirm(client, monkeypatch):
    monkeypatch.setattr(config, "EXTRACTOR", "baseline")
    text = "Reminder: appointment Thu 12 Nov at 2:40pm. Glenview Medical Practice, 4 Mill Lane, Glenview, KY99 2CD"
    r = client.post("/extract", json={"text": text, "reference_date": "2026-11-10"})
    assert r.status_code == 200
    body = r.json()
    assert body["date"] == "2026-11-12" and body["time"] == "14:40"
    assert body["needs_confirmation"] is True

    # The letter text is never stored, only the extracted fields.
    with client.session_factory() as db:
        row = db.get(Extraction, body["id"])
        assert row.confirmed is None
        assert text not in json.dumps(row.extracted)

    c = client.post(f"/extract/{body['id']}/confirm", json={"date": "2026-11-12", "time": "14:45"})
    assert c.status_code == 200 and c.json()["confirmed"]["time"] == "14:45"
    assert client.post("/extract/nope/confirm", json={}).status_code == 404
    assert client.post(f"/extract/{body['id']}/confirm", json={"date": "12/11/2026"}).status_code == 422


def test_extract_llm_through_api(client, monkeypatch):
    monkeypatch.setattr(config, "EXTRACTOR", "llm")
    answer = {"date": "2026-12-01", "time": "09:15", "clinic": "Strathmore Health Centre", "address": None}
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={"message": {"content": json.dumps(answer)}}))
    real = extractor_llm.httpx.Client
    monkeypatch.setattr(extractor_llm.httpx, "Client", lambda **kw: real(transport=transport))
    r = client.post("/extract", json={"text": "anything"})
    assert r.status_code == 200 and r.json()["clinic"] == "Strathmore Health Centre"
    assert r.json()["backend"] == "llm"


def test_llm_down_gives_502(client, monkeypatch):
    monkeypatch.setattr(config, "EXTRACTOR", "llm")
    transport = httpx.MockTransport(lambda req: httpx.Response(500))
    real = extractor_llm.httpx.Client
    monkeypatch.setattr(extractor_llm.httpx, "Client", lambda **kw: real(transport=transport))
    assert client.post("/extract", json={"text": "anything"}).status_code == 502


def test_empty_text_rejected(client):
    assert client.post("/extract", json={"text": ""}).status_code == 422
