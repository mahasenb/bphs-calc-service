"""
Deterministic golden tests for the calc service endpoints.
Run: pytest tests/ -v
After first successful run, freeze the actual values in the assertions.
"""
import os
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("CALC_SERVICE_TOKEN", "test")
os.environ.setdefault("PUBLIC_SOURCE_URL", "https://example.com")

from app.main import app
from tests.conftest import SAMPLE_A, SAMPLE_B, SAMPLE_C

client = TestClient(app, headers={"Authorization": "Bearer test"})


# ---------------------------------------------------------------------------
# /healthz
# ---------------------------------------------------------------------------

def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# /source
# ---------------------------------------------------------------------------

def test_source():
    r = client.get("/source")
    assert r.status_code == 200
    body = r.json()
    assert body["license"] == "AGPL-3.0"
    assert "source_url" in body
    assert "commit" in body


# ---------------------------------------------------------------------------
# /v1/chart — structural tests (golden numerics added after first run)
# ---------------------------------------------------------------------------

def test_chart_sample_a_structure():
    r = client.post("/v1/chart", json=SAMPLE_A)
    assert r.status_code == 200
    body = r.json()
    assert body["lagna"] in [
        "Aries","Taurus","Gemini","Cancer","Leo","Virgo",
        "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"
    ]
    assert len(body["rasi"]) == 9   # 9 planets
    assert body["ayanamsa_value"] > 20.0  # Lahiri ~23-24° in modern era


def test_chart_deterministic():
    r1 = client.post("/v1/chart", json=SAMPLE_A)
    r2 = client.post("/v1/chart", json=SAMPLE_A)
    assert r1.json() == r2.json()


# ---------------------------------------------------------------------------
# /v1/strength
# ---------------------------------------------------------------------------

def test_strength_sample_a():
    r = client.post("/v1/strength", json=SAMPLE_A)
    assert r.status_code == 200
    body = r.json()
    assert len(body["shadbala"]) == 7   # 7 classical planets
    assert len(body["bhavabala"]) == 12
    for item in body["shadbala"]:
        assert "total_bala" in item
        assert isinstance(item["is_below_minimum"], bool)


# ---------------------------------------------------------------------------
# /v1/dashas
# ---------------------------------------------------------------------------

def test_dashas_sample_a():
    req = {**SAMPLE_A, "from_date": "2020-01-01", "to_date": "2030-01-01",
           "systems": ["vimshottari"]}
    r = client.post("/v1/dashas", json=req)
    assert r.status_code == 200
    periods = r.json()
    assert len(periods) > 0
    for p in periods:
        assert p["system"] == "vimshottari"
        assert p["level"] in ("mahadasha", "antardasha")


# ---------------------------------------------------------------------------
# /v1/yogas
# ---------------------------------------------------------------------------

def test_yogas_sample_a():
    r = client.post("/v1/yogas", json=SAMPLE_A)
    assert r.status_code == 200
    yogas = r.json()
    assert isinstance(yogas, list)
    for y in yogas:
        assert "name" in y
        assert "is_viparita_raja" in y


# ---------------------------------------------------------------------------
# /v1/transits
# ---------------------------------------------------------------------------

def test_transits_sample_a():
    req = {**SAMPLE_A, "at_date": "2025-01-01"}
    r = client.post("/v1/transits", json=req)
    assert r.status_code == 200
    body = r.json()
    assert "saturn_sign" in body
    assert "sade_sati_active" in body


# ---------------------------------------------------------------------------
# /v1/special-points
# ---------------------------------------------------------------------------

def test_special_points_sample_a():
    r = client.post("/v1/special-points", json=SAMPLE_A)
    assert r.status_code == 200
    body = r.json()
    assert "arudha_lagna" in body
    assert "atmakaraka" in body
    assert body["atmakaraka"] in [
        "Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn"
    ]


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def test_auth_rejected():
    bad_client = TestClient(app, headers={"Authorization": "Bearer wrong"})
    r = bad_client.post("/v1/chart", json=SAMPLE_A)
    assert r.status_code == 401
