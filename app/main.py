import os
import subprocess
from datetime import datetime, time, date
from functools import lru_cache

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from .auth import require_token
from .schemas import (
    PersonalDataIn, DashaRequest, TransitRequest,
    ChartResponse, StrengthResponse, DashaPeriodOut,
    YogaOut, TransitResponse, SpecialPointsResponse, SourceInfo,
    PlanetPlacement, ShadbalaItem, BhavabalaItem,
    MuhurtRequest, MuhurtResponse,
)
from bphs_core.chart import Chart, PersonalData, ChartSnapshot, PlanetData
from bphs_core import strength as strength_mod
from bphs_core import dashas as dashas_mod
from bphs_core import yogas as yogas_mod
from bphs_core import transits as transits_mod
from bphs_core import special_points as sp_mod
from bphs_core import muhurat as muhurat_mod
from bphs_core import utils


app = FastAPI(
    title="Open Vedic Calc",
    description="Generic BPHS calculation service — AGPL-3.0",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

AUTH = [Depends(require_token)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_personal_data(p: PersonalDataIn) -> PersonalData:
    bd = datetime.strptime(p.birth_date, "%Y-%m-%d")
    bt = time.fromisoformat(p.birth_time)
    return PersonalData(
        name=p.name,
        birth_date=bd,
        birth_time=bt,
        birth_place=p.birth_place,
        latitude=p.latitude,
        longitude=p.longitude,
        timezone_offset_hours=p.timezone_offset_hours,
    )


def _pd_to_schema(pd: PlanetData) -> PlanetPlacement:
    return PlanetPlacement(
        planet=pd.planet, sign=pd.sign, degrees=pd.degrees,
        nakshatra=pd.nakshatra, dignity=pd.dignity, house=pd.house,
        conjunctions=pd.conjunctions, aspects=pd.aspects,
        is_retrograde=pd.is_retrograde,
    )


def _chart_to_response(s: ChartSnapshot) -> ChartResponse:
    def to_list(varga: dict) -> list[PlanetPlacement]:
        return [_pd_to_schema(pd) for pd in varga.values()]

    return ChartResponse(
        lagna=s.lagna, lagna_lord=s.lagna_lord,
        ayanamsa_value=s.ayanamsa_value,
        rasi=to_list(s.rasi_chart),
        hora=to_list(s.hora_chart),
        drekkana=to_list(s.drekkana_chart),
        saptamsa=to_list(s.saptamsa_chart),
        navamsa=to_list(s.navamsa_chart),
        decamsa=to_list(s.decamsa_chart),
        dwadasamsa=to_list(s.dwadasamsa_chart),
        chaturvimsa=to_list(s.chaturvimsa_chart),
        trimshamsa=to_list(s.trimshamsa_chart),
        shashtyamsa=to_list(s.shashtyamsa_chart),
    )


def _get_chart(p: PersonalDataIn) -> tuple[Chart, ChartSnapshot]:
    person = _to_personal_data(p)
    chart = Chart(person)
    return chart, chart.snapshot()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/v1/chart", response_model=ChartResponse, dependencies=AUTH)
def chart_endpoint(p: PersonalDataIn):
    _, s = _get_chart(p)
    return _chart_to_response(s)


@app.post("/v1/strength", response_model=StrengthResponse, dependencies=AUTH)
def strength_endpoint(p: PersonalDataIn):
    _, s = _get_chart(p)

    planets_with_shadbala = [
        pl for pl in strength_mod.SHADBALA_MINIMUMS if pl in s.rasi_chart
    ]
    shadbala = [
        ShadbalaItem(**vars(strength_mod.compute_shadbala(s, pl)))
        for pl in planets_with_shadbala
    ]
    bhavabala = [
        BhavabalaItem(**vars(r))
        for r in strength_mod.compute_all_bhavabala(s)
    ]
    akv = strength_mod.compute_ashtakavarga(s)

    return StrengthResponse(
        shadbala=shadbala,
        bhavabala=bhavabala,
        ashtakavarga=akv,
    )


@app.post("/v1/dashas", response_model=list[DashaPeriodOut], dependencies=AUTH)
def dashas_endpoint(req: DashaRequest):
    person = _to_personal_data(req)
    _, s = _get_chart(req)
    start = datetime.strptime(req.from_date, "%Y-%m-%d")
    end = datetime.strptime(req.to_date, "%Y-%m-%d")
    periods = dashas_mod.get_dasha_timeline(s, start, end, req.systems)
    return [
        DashaPeriodOut(
            lord=d.lord, level=d.level, system=d.system,
            start_date=d.start_date, end_date=d.end_date,
            duration_years=d.duration_years,
        )
        for d in periods
    ]


@app.post("/v1/yogas", response_model=list[YogaOut], dependencies=AUTH)
def yogas_endpoint(p: PersonalDataIn):
    _, s = _get_chart(p)
    yogas = yogas_mod.detect_all_yogas(s)
    return [
        YogaOut(
            name=y.name, description=y.description,
            planets_involved=y.planets_involved,
            houses_involved=y.houses_involved,
            strength=y.strength,
            is_viparita_raja=y.is_viparita_raja,
        )
        for y in yogas
    ]


@app.post("/v1/transits", response_model=TransitResponse, dependencies=AUTH)
def transits_endpoint(req: TransitRequest):
    _, s = _get_chart(req)
    at = datetime.strptime(req.at_date, "%Y-%m-%d")

    current = transits_mod.get_current_transits(s, at)
    saturn = current.get("Saturn")
    jupiter = current.get("Jupiter")

    sade_sati = transits_mod.get_sade_sati_info(s, at)

    saturn_vedha = transits_mod.check_ashtakavarga_vedha(s, "Saturn",
                                                          saturn.sign if saturn else "")
    jupiter_vedha = transits_mod.check_ashtakavarga_vedha(s, "Jupiter",
                                                           jupiter.sign if jupiter else "")

    return TransitResponse(
        saturn_sign=saturn.sign if saturn else "",
        jupiter_sign=jupiter.sign if jupiter else "",
        sade_sati_active=sade_sati.is_active,
        sade_sati_phase=sade_sati.phase if sade_sati.is_active else None,
        saturn_vedha_blocked=saturn_vedha,
        jupiter_vedha_blocked=jupiter_vedha,
    )


@app.post("/v1/special-points", response_model=SpecialPointsResponse, dependencies=AUTH)
def special_points_endpoint(p: PersonalDataIn):
    _, s = _get_chart(p)
    return SpecialPointsResponse(
        arudha_lagna=sp_mod.get_arudha_lagna(s).sign,
        upapada=sp_mod.get_upapada(s).sign,
        atmakaraka=sp_mod.get_atmakaraka(s),
        karakamsa=sp_mod.get_karakamsa(s).sign,
    )


@app.post("/v1/muhurat", response_model=MuhurtResponse, dependencies=AUTH)
def muhurat_endpoint(req: MuhurtRequest):
    _, s = _get_chart(req)
    
    # Extract natal Moon's nakshatra and sign from Rasi chart
    moon_pd = s.rasi_chart.get("Moon")
    birth_nak = moon_pd.nakshatra if moon_pd else None
    birth_sign = moon_pd.sign if moon_pd else None
    
    # Parse date range
    start_dt = datetime.strptime(req.start_date, "%Y-%m-%d").date()
    end_dt = datetime.strptime(req.end_date, "%Y-%m-%d").date()
    
    # Loop over date range
    from datetime import timedelta
    days = []
    curr = start_dt
    place = utils.make_place(req.name, req.latitude, req.longitude, req.timezone_offset_hours)
    
    while curr <= end_dt:
        day_data = muhurat_mod.compute_muhurat_for_day(
            place=place,
            target_date=curr,
            birth_nakshatra=birth_nak,
            birth_moon_sign=birth_sign
        )
        days.append(day_data)
        curr += timedelta(days=1)
        
    return MuhurtResponse(days=days)


@app.get("/healthz")
def healthz():
    ephe_ok = os.path.isdir(os.path.join(os.path.dirname(__file__), "../data/ephe"))
    return {"status": "ok", "ephe_loaded": ephe_ok}


@app.get("/source", response_model=SourceInfo)
def source():
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        commit = "unknown"

    return SourceInfo(
        source_url=os.environ.get("PUBLIC_SOURCE_URL", "https://github.com/your-org/bphs-calc-service"),
        commit=commit,
    )
