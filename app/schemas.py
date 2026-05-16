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
    navamsa: list[PlanetPlacement]
    decamsa: list[PlanetPlacement]
    dwadasamsa: list[PlanetPlacement]
    chaturvimsa: list[PlanetPlacement]
    trimshamsa: list[PlanetPlacement]
    shashtyamsa: list[PlanetPlacement]


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
