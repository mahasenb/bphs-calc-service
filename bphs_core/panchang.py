"""Panchang (Hindu almanac) computation for Muhurta / electional astrology.

This module provides the missing almanac data (tithi, nakshatra, yoga, karana, vara)
that the LLM needs to answer questions about auspicious times.

All functions are pure and deterministic. They use the same Lahiri ayanamsa
and Swiss Ephemeris configuration as the rest of bphs_core.

Design notes:
- Tithi, Yoga and Karana are derived from the angular separation of Sun and Moon.
- Nakshatra and Vara are straightforward.
- The dataclass is intentionally lightweight so it can be easily JSON-serialized
  and passed through the LLM context.
"""

from dataclasses import dataclass
from datetime import datetime
import swisseph as swe
from . import utils


# Classical Panchang elements (order matters for indexing)
TITHIS = [
    "Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami",
    "Shashthi", "Saptami", "Ashtami", "Navami", "Dashami",
    "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi", "Purnima",  # Shukla
    "Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami",
    "Shashthi", "Saptami", "Ashtami", "Navami", "Dashami",
    "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi", "Amavasya",  # Krishna
]

YOGAS = [
    "Vishkambha", "Priti", "Ayushman", "Saubhagya", "Shobhana",
    "Atiganda", "Sukarman", "Dhriti", "Shula", "Ganda",
    "Vriddhi", "Dhruva", "Vyaghata", "Harshana", "Vajra",
    "Vyatipata", "Variyana", "Parigha", "Shiva", "Siddha",
    "Sadhya", "Shubha", "Shukla", "Brahma", "Indra",
    "Vaidhriti",
]

KARANAS = [
    "Bava", "Balava", "Kaulava", "Taitila", "Gara",
    "Vanija", "Vishti", "Shakuni", "Chatushpada", "Naga",
    "Kimstughna",
]

WEEKDAYS = [
    "Sunday", "Monday", "Tuesday", "Wednesday",
    "Thursday", "Friday", "Saturday",
]


@dataclass
class Panchang:
    """Computed Panchang for a given date/time."""

    date: str                      # YYYY-MM-DD
    tithi: str
    tithi_number: int              # 1-30 (1 = Pratipada Shukla, 15 = Purnima, 30 = Amavasya)
    paksha: str                    # "Shukla" or "Krishna"
    vara: str                      # Weekday
    nakshatra: str
    nakshatra_lord: str            # Classical lord of the nakshatra
    yoga: str
    karana: str
    # Optional lightweight tags the LLM can use for quick filtering
    is_auspicious_for: list[str]   # e.g. ["business", "travel", "marriage"] — conservative defaults


# Nakshatra lords (repeating every 3 nakshatras)
_NAKSHATRA_LORDS = {
    "Ashwini": "Ketu", "Bharani": "Venus", "Krittika": "Sun",
    "Rohini": "Moon", "Mrigashira": "Mars", "Ardra": "Rahu",
    "Punarvasu": "Jupiter", "Pushya": "Saturn", "Ashlesha": "Mercury",
    "Magha": "Ketu", "Purva Phalguni": "Venus", "Uttara Phalguni": "Sun",
    "Hasta": "Moon", "Chitra": "Mars", "Swati": "Rahu",
    "Vishakha": "Jupiter", "Anuradha": "Saturn", "Jyeshtha": "Mercury",
    "Mula": "Ketu", "Purva Ashadha": "Venus", "Uttara Ashadha": "Sun",
    "Shravana": "Moon", "Dhanishta": "Mars", "Shatabhisha": "Rahu",
    "Purva Bhadrapada": "Jupiter", "Uttara Bhadrapada": "Saturn", "Revati": "Mercury",
}


def _jd_from_date(dt: datetime) -> float:
    """Return Julian Day for the given local datetime (no timezone conversion)."""
    return swe.julday(
        dt.year, dt.month, dt.day,
        dt.hour + dt.minute / 60.0 + dt.second / 3600.0
    )


def _get_sun_moon_longitudes(jd: float) -> tuple[float, float]:
    """Return sidereal longitudes (degrees) of Sun and Moon."""
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    flags = swe.FLG_SIDEREAL

    sun_result, _ = swe.calc_ut(jd, swe.SUN, flags)
    moon_result, _ = swe.calc_ut(jd, swe.MOON, flags)

    sun_lon = sun_result[0] % 360.0
    moon_lon = moon_result[0] % 360.0
    return sun_lon, moon_lon


def _compute_tithi(sun_lon: float, moon_lon: float) -> tuple[str, int, str]:
    """Return (tithi_name, tithi_number 1-30, paksha)."""
    diff = (moon_lon - sun_lon) % 360.0
    tithi_num = int(diff / 12.0) + 1          # 1..30
    if tithi_num > 30:
        tithi_num = 30

    # Paksha
    paksha = "Shukla" if tithi_num <= 15 else "Krishna"

    # Map to name (TITHIS has two sets)
    name_index = (tithi_num - 1) % 15
    tithi_name = TITHIS[tithi_num - 1]
    return tithi_name, tithi_num, paksha


def _compute_yoga(sun_lon: float, moon_lon: float) -> str:
    """Return the Panchang Yoga name."""
    total = (sun_lon + moon_lon) % 360.0
    yoga_index = int(total / (360.0 / 27.0)) % 27
    return YOGAS[yoga_index]


def _compute_karana(sun_lon: float, moon_lon: float) -> str:
    """Return the Karana name (half-tithi)."""
    diff = (moon_lon - sun_lon) % 360.0
    karana_index = int(diff / 6.0) % 11          # 0..10
    return KARANAS[karana_index]


def get_panchang(at: datetime) -> Panchang:
    """Compute full Panchang for the given datetime."""
    jd = _jd_from_date(at)
    sun_lon, moon_lon = _get_sun_moon_longitudes(jd)

    tithi_name, tithi_num, paksha = _compute_tithi(sun_lon, moon_lon)
    nakshatra = utils.longitude_to_nakshatra(moon_lon)
    nakshatra_lord = _NAKSHATRA_LORDS.get(nakshatra, "Unknown")
    yoga = _compute_yoga(sun_lon, moon_lon)
    karana = _compute_karana(sun_lon, moon_lon)
    vara = WEEKDAYS[at.weekday()]

    # Very conservative default auspiciousness tags (LLM can override with chart context)
    auspicious = []
    if tithi_num in (1, 2, 3, 5, 7, 10, 11, 13, 15):
        auspicious.append("general")
    if nakshatra_lord in ("Jupiter", "Venus", "Moon"):
        auspicious.append("auspicious")
    if "Shubha" in yoga or "Siddha" in yoga:
        auspicious.append("business")

    return Panchang(
        date=at.strftime("%Y-%m-%d"),
        tithi=tithi_name,
        tithi_number=tithi_num,
        paksha=paksha,
        vara=vara,
        nakshatra=nakshatra,
        nakshatra_lord=nakshatra_lord,
        yoga=yoga,
        karana=karana,
        is_auspicious_for=sorted(set(auspicious)),
    )