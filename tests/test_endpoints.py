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

_VALID_SIGNS = {
    "Aries","Taurus","Gemini","Cancer","Leo","Virgo",
    "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"
}


def test_chart_sample_a_structure():
    r = client.post("/v1/chart", json=SAMPLE_A)
    assert r.status_code == 200
    body = r.json()
    assert body["lagna"] in _VALID_SIGNS
    assert len(body["rasi"]) == 9   # 9 planets
    assert body["ayanamsa_value"] > 20.0  # Lahiri ~23-24° in modern era


def test_chart_new_vargas():
    """D2/D3/D7/D12 must be present and well-formed."""
    r = client.post("/v1/chart", json=SAMPLE_A)
    assert r.status_code == 200
    body = r.json()
    for varga in ("hora", "drekkana", "saptamsa", "dwadasamsa"):
        assert varga in body, f"Missing varga: {varga}"
        assert len(body[varga]) == 9, f"{varga} must have 9 planet entries"
        for p in body[varga]:
            assert p["sign"] in _VALID_SIGNS, f"{varga}/{p['planet']} invalid sign: {p['sign']}"

    # D2 Hora — every planet must be Cancer or Leo (the only two hora signs)
    for p in body["hora"]:
        assert p["sign"] in ("Cancer", "Leo"), (
            f"Hora sign must be Cancer or Leo, got {p['sign']} for {p['planet']}"
        )


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
# /v1/muhurat
# ---------------------------------------------------------------------------

def test_muhurat_endpoint():
    req = {
        **SAMPLE_A,
        "start_date": "2026-05-26",
        "end_date": "2026-05-28"
    }
    r = client.post("/v1/muhurat", json=req)
    assert r.status_code == 200
    body = r.json()
    assert "days" in body
    assert len(body["days"]) == 3
    
    first_day = body["days"][0]
    assert first_day["date"] == "2026-05-26"
    assert "sunrise" in first_day
    assert "sunset" in first_day
    assert "panchanga" in first_day
    assert "auspicious_muhurtas" in first_day
    assert "chogadiya" in first_day
    assert "inauspicious_periods" in first_day
    assert "personal_balam" in first_day
    assert "tara_bala" in first_day["personal_balam"]
    assert "chandra_bala" in first_day["personal_balam"]


# ---------------------------------------------------------------------------
# /v1/muhurat/lagna-shuddhi
# ---------------------------------------------------------------------------

_LAGNA_SHUDDHI_REQ = {
    **SAMPLE_A,
    "start_date": "2026-05-26",
    "end_date": "2026-05-28",
    "activity_category": "generic",
    "step_seconds": 60,
}

_VALID_DIGNITIES = {
    "exalted", "moolatrikona", "own sign", "friendly", "neutral", "enemy",
    "debilitated", "unknown",
}


def test_lagna_shuddhi_structure():
    r = client.post("/v1/muhurat/lagna-shuddhi", json=_LAGNA_SHUDDHI_REQ)
    assert r.status_code == 200
    body = r.json()
    assert "best_instant" in body
    assert "best_window" in body
    assert "top_samples" in body

    bi = body["best_instant"]
    assert bi is not None
    assert "instant" in bi        # "YYYY-MM-DD HH:MM"
    assert "lagna_sign" in bi
    assert "lagna_lord" in bi
    assert "score" in bi
    assert 0.0 <= bi["score"] <= 1.0
    assert bi["lagna_sign"] in _VALID_SIGNS
    assert bi["lagna_lord_dignity"] in _VALID_DIGNITIES

    bw = body["best_window"]
    assert bw is not None
    assert "start" in bw
    assert "end" in bw
    # Window must be ≤ 11 minutes wide (band_start to band_end+1)
    from datetime import datetime
    s = datetime.strptime(bw["start"], "%H:%M")
    e = datetime.strptime(bw["end"], "%H:%M")
    width_mins = (e.hour * 60 + e.minute) - (s.hour * 60 + s.minute)
    assert width_mins <= 11, f"Window too wide: {width_mins} min"

    assert isinstance(body["top_samples"], list)
    assert len(body["top_samples"]) <= 20


def test_lagna_shuddhi_returns_minute_resolution():
    r = client.post("/v1/muhurat/lagna-shuddhi", json=_LAGNA_SHUDDHI_REQ)
    body = r.json()
    bi = body["best_instant"]
    # instant format is "YYYY-MM-DD HH:MM" — must resolve to a specific minute
    parts = bi["instant"].split(" ")
    assert len(parts) == 2
    assert len(parts[1]) == 5  # "HH:MM"


def test_lagna_shuddhi_best_not_in_rahu_kala():
    """Best instant should never be inside Rahu Kala."""
    r = client.post("/v1/muhurat/lagna-shuddhi", json=_LAGNA_SHUDDHI_REQ)
    body = r.json()
    bi = body["best_instant"]
    assert not bi["in_rahu_kala"], "Best instant must not be in Rahu Kala"
    assert not bi["in_yamaganda"], "Best instant must not be in Yamaganda"
    assert not bi["in_gulika"], "Best instant must not be in Gulika"


def test_lagna_shuddhi_top_samples_ordered():
    """top_samples must be sorted by score descending."""
    r = client.post("/v1/muhurat/lagna-shuddhi", json=_LAGNA_SHUDDHI_REQ)
    body = r.json()
    scores = [s["score"] for s in body["top_samples"]]
    assert scores == sorted(scores, reverse=True), "top_samples not sorted by score desc"


def test_lagna_shuddhi_activity_categories():
    """All activity categories must return 200 with valid structure."""
    for activity in ["generic", "business", "marriage", "travel", "surgery"]:
        req = {**_LAGNA_SHUDDHI_REQ, "activity_category": activity}
        r = client.post("/v1/muhurat/lagna-shuddhi", json=req)
        assert r.status_code == 200, f"Failed for activity={activity}"
        body = r.json()
        assert body["best_instant"] is not None or body["top_samples"] == []


def test_lagna_shuddhi_surgery_excludes_rahu_varjyam():
    """Surgery mode: no sample in top_samples should have Rahu Kala or Varjyam."""
    req = {**_LAGNA_SHUDDHI_REQ, "activity_category": "surgery"}
    r = client.post("/v1/muhurat/lagna-shuddhi", json=req)
    body = r.json()
    for sample in body["top_samples"]:
        assert not sample["in_rahu_kala"]
        assert not sample["in_varjyam"]
        assert not sample["in_durmuhurtam"]


# ---------------------------------------------------------------------------
# /v1/compat
# ---------------------------------------------------------------------------

_COMPAT_REQ = {"person_a": SAMPLE_A, "person_b": SAMPLE_B}

_VALID_SEVERITY = {"none", "mild", "strong"}
_VALID_QUALITY  = {"favorable", "neutral", "challenging"}
_KUTA_NAMES     = ["varna", "vasya", "tara", "yoni", "graha_maitri", "gana", "bhakoot", "nadi"]
_KUTA_MAX       = {"varna": 1, "vasya": 2, "tara": 3, "yoni": 4,
                   "graha_maitri": 5, "gana": 6, "bhakoot": 7, "nadi": 8}


def test_compat_structure():
    r = client.post("/v1/compat", json=_COMPAT_REQ)
    assert r.status_code == 200
    body = r.json()

    # top-level fields
    assert "total_score" in body
    assert "max_score" in body
    assert "kutas" in body
    assert "mangal_dosha_a" in body
    assert "mangal_dosha_b" in body
    assert "nakshatra_compatibility" in body
    assert "dasha_overlaps" in body
    assert "composite_strength_notes" in body


def test_compat_max_score_36():
    r = client.post("/v1/compat", json=_COMPAT_REQ)
    assert r.status_code == 200
    assert r.json()["max_score"] == 36.0


def test_compat_total_equals_sum_of_kutas():
    r = client.post("/v1/compat", json=_COMPAT_REQ)
    assert r.status_code == 200
    body = r.json()
    expected = round(sum(k["score"] for k in body["kutas"]), 4)
    assert round(body["total_score"], 4) == expected


def test_compat_kutas_well_formed():
    r = client.post("/v1/compat", json=_COMPAT_REQ)
    assert r.status_code == 200
    kutas = r.json()["kutas"]
    assert len(kutas) == 8
    names = [k["name"] for k in kutas]
    assert names == _KUTA_NAMES
    for k in kutas:
        assert k["max_score"] == _KUTA_MAX[k["name"]]
        assert 0.0 <= k["score"] <= k["max_score"]
        assert isinstance(k["interpretation"], str)
        assert len(k["interpretation"]) > 0


def test_compat_mangal_dosha_well_formed():
    r = client.post("/v1/compat", json=_COMPAT_REQ)
    assert r.status_code == 200
    body = r.json()
    for key in ("mangal_dosha_a", "mangal_dosha_b"):
        d = body[key]
        assert isinstance(d["has_dosha"], bool)
        assert d["severity"] in _VALID_SEVERITY
        assert isinstance(d["cancellation"], str)
        if not d["has_dosha"]:
            assert d["severity"] == "none"


def test_compat_dasha_overlaps_well_formed():
    r = client.post("/v1/compat", json=_COMPAT_REQ)
    assert r.status_code == 200
    overlaps = r.json()["dasha_overlaps"]
    assert isinstance(overlaps, list)
    for o in overlaps:
        assert "start_date" in o and "end_date" in o
        assert o["quality"] in _VALID_QUALITY
        assert o["start_date"] <= o["end_date"]


def test_compat_deterministic():
    r1 = client.post("/v1/compat", json=_COMPAT_REQ)
    r2 = client.post("/v1/compat", json=_COMPAT_REQ)
    assert r1.json() == r2.json()


def test_compat_unauthenticated():
    bad_client = TestClient(app, headers={"Authorization": "Bearer wrong"})
    r = bad_client.post("/v1/compat", json=_COMPAT_REQ)
    assert r.status_code == 401


def test_compat_missing_fields():
    r = client.post("/v1/compat", json={"person_a": SAMPLE_A})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def test_auth_rejected():
    bad_client = TestClient(app, headers={"Authorization": "Bearer wrong"})
    r = bad_client.post("/v1/chart", json=SAMPLE_A)
    assert r.status_code == 401

