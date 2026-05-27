from typing import Literal
from pydantic import BaseModel
from datetime import datetime


class PersonalDataIn(BaseModel):
    name: str
    birth_date: str            # ISO date YYYY-MM-DD
    birth_time: str            # HH:MM:SS local time
    birth_place: str
    latitude: float
    longitude: float
    timezone_offset_hours: float


class DashaRequest(PersonalDataIn):
    from_date: str             # ISO date
    to_date: str               # ISO date
    systems: list[str] = ["vimshottari"]


class TransitRequest(PersonalDataIn):
    at_date: str               # ISO date


# --- Chart ---

class PlanetPlacement(BaseModel):
    planet: str
    sign: str
    degrees: float
    nakshatra: str
    dignity: str
    house: int
    conjunctions: list[str]
    aspects: list[str]
    is_retrograde: bool


class ChartResponse(BaseModel):
    lagna: str
    lagna_lord: str
    ayanamsa_value: float
    rasi: list[PlanetPlacement]
    hora: list[PlanetPlacement]          # D2 — wealth/resources
    drekkana: list[PlanetPlacement]      # D3 — siblings/vitality
    saptamsa: list[PlanetPlacement]      # D7 — children/creative output
    navamsa: list[PlanetPlacement]       # D9
    decamsa: list[PlanetPlacement]       # D10
    dwadasamsa: list[PlanetPlacement]    # D12 — parents/lineage
    chaturvimsa: list[PlanetPlacement]   # D24
    trimshamsa: list[PlanetPlacement]    # D30
    shashtyamsa: list[PlanetPlacement]   # D60


# --- Strength ---

class ShadbalaItem(BaseModel):
    planet: str
    sthana_bala: float
    dig_bala: float
    kaala_bala: float
    cheshta_bala: float
    naisargika_bala: float
    drik_bala: float
    total_bala: float
    minimum_bala: float
    is_below_minimum: bool


class BhavabalaItem(BaseModel):
    house_number: int
    bala_total: float
    bhava_adhipathi_bala: float
    bhava_drik: float
    rank: str


class StrengthResponse(BaseModel):
    shadbala: list[ShadbalaItem]
    bhavabala: list[BhavabalaItem]
    ashtakavarga: dict


# --- Dashas ---

class DashaPeriodOut(BaseModel):
    lord: str
    level: str
    system: str
    start_date: datetime
    end_date: datetime
    duration_years: float


# --- Yogas ---

class YogaOut(BaseModel):
    name: str
    description: str
    planets_involved: list[str]
    houses_involved: list[int]
    strength: str
    is_viparita_raja: bool = False


# --- Transits ---

class TransitResponse(BaseModel):
    saturn_sign: str
    jupiter_sign: str
    sade_sati_active: bool
    sade_sati_phase: str | None = None
    saturn_vedha_blocked: bool
    jupiter_vedha_blocked: bool


# --- Special points ---

class SpecialPointsResponse(BaseModel):
    arudha_lagna: str
    upapada: str
    atmakaraka: str
    karakamsa: str


# --- Meta ---

class SourceInfo(BaseModel):
    license: str = "AGPL-3.0"
    source_url: str
    commit: str
    ephemeris_license: str = "Swiss Ephemeris AGPL-3.0 (data/ephe/)"


# --- Muhurat ---

class MuhurtRequest(BaseModel):
    name: str
    birth_date: str
    birth_time: str
    birth_place: str
    latitude: float
    longitude: float
    timezone_offset_hours: float
    start_date: str      # YYYY-MM-DD
    end_date: str        # YYYY-MM-DD


class TimeWindow(BaseModel):
    start: str           # HH:MM
    end: str             # HH:MM
    label: str | None = None


class PanchangaInfo(BaseModel):
    tithi: str
    tithi_end: str
    nakshatra: str
    nakshatra_end: str
    yogam: str
    yogam_end: str
    karana: str
    karana_end: str
    vaara: str


class PersonalBalam(BaseModel):
    tara_bala: str
    chandra_bala: str


class DayMuhurat(BaseModel):
    date: str            # YYYY-MM-DD
    sunrise: str
    sunset: str
    moonrise: str | None = None
    moonset: str | None = None
    panchanga: PanchangaInfo
    auspicious_muhurtas: list[TimeWindow]
    chogadiya: list[TimeWindow]
    inauspicious_periods: list[TimeWindow]
    amrita_periods: list[TimeWindow]
    panchaka_free: bool
    personal_balam: PersonalBalam | None = None
    all_muhurtas: list[TimeWindow]


class MuhurtResponse(BaseModel):
    days: list[DayMuhurat]


# --- Compatibility ---

class CompatRequest(BaseModel):
    person_a: PersonalDataIn
    person_b: PersonalDataIn


class KutaScore(BaseModel):
    name: str
    score: float
    max_score: float
    interpretation: str


class MangalDoshaResult(BaseModel):
    has_dosha: bool
    severity: Literal["none", "mild", "strong"]
    cancellation: str


class DashaOverlap(BaseModel):
    start_date: str   # YYYY-MM-DD
    end_date: str     # YYYY-MM-DD
    person_a_lord: str
    person_b_lord: str
    quality: Literal["favorable", "neutral", "challenging"]


class CompatResponse(BaseModel):
    total_score: float
    max_score: float
    kutas: list[KutaScore]
    mangal_dosha_a: MangalDoshaResult
    mangal_dosha_b: MangalDoshaResult
    nakshatra_compatibility: str
    dasha_overlaps: list[DashaOverlap]
    composite_strength_notes: str

