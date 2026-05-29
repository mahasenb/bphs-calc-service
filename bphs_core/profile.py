"""BPHS single-chart profile data: Avkahada Chakra, Kalsarp Dosh,
Sade Sati lifetime scan, Numerology, and Favourable auspicious markers.

All calculations are pure Python / deterministic math — no LLM, no swe calls
except for the Sade Sati lifetime scan (which uses the transit longitude helper
from transits.py).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from .chart import ChartSnapshot
from .compat import (
    NAKSHATRA_GANA,
    NAKSHATRA_YONI,
    _VARNA_LEVEL,
    _VARNA_NAMES,
    _VASYA_GROUP,
    _nakshatra_nadi,
)
from . import utils

# Vimshottari nakshatra lords in order (27 nakshatras).
_NAK_LORDS = [
    "Ketu","Venus","Sun","Moon","Mars","Rahu","Jupiter","Saturn","Mercury",
    "Ketu","Venus","Sun","Moon","Mars","Rahu","Jupiter","Saturn","Mercury",
    "Ketu","Venus","Sun","Moon","Mars","Rahu","Jupiter","Saturn","Mercury",
]


# ---------------------------------------------------------------------------
# Avkahada Chakra — single-chart Moon-sign / Moon-nakshatra profile
# ---------------------------------------------------------------------------

def _varna(moon_sign: str) -> str:
    level = _VARNA_LEVEL.get(moon_sign, 0)
    return _VARNA_NAMES.get(level, "Unknown")


def _vasya(moon_sign: str) -> str:
    return _VASYA_GROUP.get(moon_sign, "Unknown")


def _yoni(moon_nak: str) -> str:
    pair = NAKSHATRA_YONI.get(moon_nak)
    if not pair:
        return "Unknown"
    animal, gender = pair
    return f"{animal} ({gender})"


def _gana(moon_nak: str) -> str:
    return NAKSHATRA_GANA.get(moon_nak, "Unknown")


def _nadi(moon_nak: str) -> str:
    try:
        return _nakshatra_nadi(moon_nak)
    except (ValueError, IndexError):
        return "Unknown"


def avkahada_chakra(snapshot: ChartSnapshot) -> dict:
    """Return Avkahada Chakra parameters for a single chart.

    All five parameters are derived from the Moon's sign and nakshatra.
    """
    moon = snapshot.rasi_chart.get("Moon")
    if not moon:
        return {}
    nak = moon.nakshatra
    sign = moon.sign
    nak_idx = utils.NAKSHATRAS.index(nak) if nak in utils.NAKSHATRAS else -1
    return {
        "moon_sign":  sign,
        "moon_nakshatra": nak,
        "varna":      _varna(sign),
        "vasya":      _vasya(sign),
        "yoni":       _yoni(nak),
        "gana":       _gana(nak),
        "nadi":       _nadi(nak),
        "nakshatra_lord": _NAK_LORDS[nak_idx] if 0 <= nak_idx < len(_NAK_LORDS) else "",
    }


# ---------------------------------------------------------------------------
# Kalsarp Dosh
# ---------------------------------------------------------------------------

_SEVEN_PLANETS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")

# Named Kalsarp types by Rahu house (whole-sign from lagna)
_KALSARP_NAMES = {
    1: "Anant Kalsarp",    2: "Kulik Kalsarp",   3: "Vasuki Kalsarp",
    4: "Shankhapal Kalsarp", 5: "Padma Kalsarp",  6: "Mahapadma Kalsarp",
    7: "Takshak Kalsarp",  8: "Karkotak Kalsarp", 9: "Shankhachur Kalsarp",
    10: "Ghatak Kalsarp", 11: "Vishakta Kalsarp", 12: "Sheshnag Kalsarp",
}


def kalsarp_dosh(snapshot: ChartSnapshot) -> dict:
    """Check for Kalsarp Dosh: all 7 visible planets hemmed between Rahu and Ketu.

    Kalsarp Dosh is present when every planet (Sun–Saturn) occupies the 180°
    arc from Rahu to Ketu (measured clockwise). The reciprocal case (all in the
    Ketu→Rahu arc) is sometimes called Kalsarp but is considered less severe
    (Kalasarpa vs Kalsarp — we label it partial). Any planet exactly on Rahu
    or Ketu dissolves the yoga.
    """
    rahu = snapshot.rasi_chart.get("Rahu")
    if not rahu:
        return {"present": False, "name": None, "partial": False, "rahu_house": None}

    rahu_lon = utils.SIGNS.index(rahu.sign) * 30 + rahu.degrees
    ketu_lon = (rahu_lon + 180) % 360

    in_rahu_ketu_arc: list[bool] = []
    for name in _SEVEN_PLANETS:
        p = snapshot.rasi_chart.get(name)
        if not p:
            continue
        p_lon = utils.SIGNS.index(p.sign) * 30 + p.degrees
        # Planet is in arc if (p_lon - rahu_lon) mod 360 < 180
        in_arc = (p_lon - rahu_lon) % 360 < 180
        in_rahu_ketu_arc.append(in_arc)

    if not in_rahu_ketu_arc:
        return {"present": False, "name": None, "partial": False, "rahu_house": None}

    all_in = all(in_rahu_ketu_arc)
    all_out = not any(in_rahu_ketu_arc)   # all in Ketu→Rahu arc
    rahu_house = rahu.house

    if all_in or all_out:
        name = _KALSARP_NAMES.get(rahu_house, "Kalsarp")
        return {"present": True, "name": name, "partial": False, "rahu_house": rahu_house,
                "direction": "rahu_to_ketu" if all_in else "ketu_to_rahu"}
    return {"present": False, "name": None, "partial": True, "rahu_house": rahu_house}


# ---------------------------------------------------------------------------
# Sade Sati lifetime scan
# ---------------------------------------------------------------------------

def sade_sati_lifetime(snapshot: ChartSnapshot, birth_date: date) -> list[dict]:
    """Return all Sade Sati periods from birth to birth+80 years.

    Scans every ~91 days (quarterly) for Saturn's sign relative to natal Moon.
    Contiguous quarters where Saturn occupies the sign before, same as, or after
    natal Moon are merged into a single period with a rising/peak/setting label.
    """
    from .transits import _transit_longitude, _jd_from_date

    moon = snapshot.rasi_chart.get("Moon")
    if not moon or moon.sign not in utils.SIGNS:
        return []

    moon_idx = utils.SIGNS.index(moon.sign)

    # Quarter-year steps over 80 years
    periods: list[dict] = []
    step = timedelta(days=91)
    scan_date = datetime(birth_date.year, birth_date.month, birth_date.day)
    end_date = datetime(birth_date.year + 80, birth_date.month, birth_date.day)

    active: dict | None = None  # current open Sade Sati window
    prev_phase: str | None = None

    while scan_date <= end_date:
        try:
            jd = _jd_from_date(scan_date)
            sat_lon = _transit_longitude(jd, 6)  # Saturn
            sat_idx = int(sat_lon // 30) % 12
        except Exception:
            scan_date += step
            continue

        diff = (sat_idx - moon_idx) % 12
        if diff == 11:
            phase = "rising"
        elif diff == 0:
            phase = "peak"
        elif diff == 1:
            phase = "setting"
        else:
            phase = None

        if phase:
            if active is None:
                active = {"phase": phase, "start": scan_date.strftime("%Y-%m-%d"),
                          "end": scan_date.strftime("%Y-%m-%d")}
            else:
                active["end"] = scan_date.strftime("%Y-%m-%d")
                if phase != prev_phase and prev_phase is not None:
                    # phase shifted inside the same continuous window — keep going
                    active["phase"] = "multi"
        else:
            if active is not None:
                periods.append(active)
                active = None
        prev_phase = phase
        scan_date += step

    if active is not None:
        periods.append(active)

    return periods


# ---------------------------------------------------------------------------
# Numerology
# ---------------------------------------------------------------------------

def _reduce(n: int) -> int:
    while n > 9:
        n = sum(int(d) for d in str(n))
    return n


def numerology(birth_date: date) -> dict:
    """Radical (Mulank) and Destiny (Bhagyank) numbers.

    Radical = digit sum of day, reduced to 1–9.
    Destiny = digit sum of full date (DDMMYYYY), reduced to 1–9.
    """
    radical = _reduce(sum(int(d) for d in str(birth_date.day)))
    destiny = _reduce(sum(int(d) for d in str(birth_date.day)
                         + str(birth_date.month)
                         + str(birth_date.year)))
    return {"radical": radical, "destiny": destiny}


# ---------------------------------------------------------------------------
# Favourable Points (Shubha Anka etc.) based on lagna lord
# ---------------------------------------------------------------------------

_LAGNA_LORD_PROFILE: dict[str, dict] = {
    "Sun":     {"lucky_number": 1,  "lucky_metal": "Gold",       "lucky_stone": "Ruby",             "lucky_color": "Red"},
    "Moon":    {"lucky_number": 2,  "lucky_metal": "Silver",     "lucky_stone": "Pearl",            "lucky_color": "White"},
    "Mars":    {"lucky_number": 9,  "lucky_metal": "Copper",     "lucky_stone": "Red Coral",        "lucky_color": "Red"},
    "Mercury": {"lucky_number": 5,  "lucky_metal": "Bronze",     "lucky_stone": "Emerald",          "lucky_color": "Green"},
    "Jupiter": {"lucky_number": 3,  "lucky_metal": "Gold",       "lucky_stone": "Yellow Sapphire",  "lucky_color": "Yellow"},
    "Venus":   {"lucky_number": 6,  "lucky_metal": "Silver",     "lucky_stone": "Diamond",          "lucky_color": "White"},
    "Saturn":  {"lucky_number": 8,  "lucky_metal": "Iron",       "lucky_stone": "Blue Sapphire",    "lucky_color": "Blue"},
    "Rahu":    {"lucky_number": 4,  "lucky_metal": "Lead",       "lucky_stone": "Hessonite",        "lucky_color": "Blue"},
    "Ketu":    {"lucky_number": 7,  "lucky_metal": "Iron",       "lucky_stone": "Cat's Eye",        "lucky_color": "Multicolor"},
}


def favourable_points(snapshot: ChartSnapshot) -> dict:
    """Return lucky number / metal / stone / color based on the Janma-rasi lord.

    Auspicious metal/gemstone are keyed on the lord of the Moon's sign (Janma
    rashi), the classical "lucky gem" rule — e.g. a Cancer Moon (lord Moon)
    yields Silver / Pearl. Falls back to the lagna lord if the Moon is absent.
    """
    moon = snapshot.rasi_chart.get("Moon")
    rasi_lord = utils.get_sign_lord(moon.sign) if moon else snapshot.lagna_lord
    profile = dict(_LAGNA_LORD_PROFILE.get(rasi_lord, {}))
    profile["rasi_lord"] = rasi_lord
    return profile


# ---------------------------------------------------------------------------
# Composite profile — single entry point
# ---------------------------------------------------------------------------

def compute_profile(snapshot: ChartSnapshot, birth_date: date) -> dict:
    return {
        "avkahada":    avkahada_chakra(snapshot),
        "kalsarp":     kalsarp_dosh(snapshot),
        "sade_sati_lifetime": sade_sati_lifetime(snapshot, birth_date),
        "numerology":  numerology(birth_date),
        "favourable":  favourable_points(snapshot),
    }
