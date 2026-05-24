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


class PanchangRequest(PersonalDataIn):
    at_date: str               # ISO date


# --- Panchang (for Muhurta / electional astrology) ---

class PanchangResponse(BaseModel):
    date: str
    tithi: str
    tithi_number: int
    paksha: str
    vara: str
    nakshatra: str
    nakshatra_lord: str
    yoga: str
    karana: str
    is_auspicious_for: list[str]


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
