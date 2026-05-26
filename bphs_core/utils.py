import os
import swisseph as swe
from jhora.panchanga import drik

EPHE_PATH = os.path.join(os.path.dirname(__file__), "../data/ephe")
swe.set_ephe_path(EPHE_PATH)

# Initialize pyjhora ayanamsa mode
drik.set_ayanamsa_mode('LAHIRI')

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

PLANETS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha",
    "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
]

SIGN_LORDS: dict[str, str] = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury",
    "Cancer": "Moon", "Leo": "Sun", "Virgo": "Mercury",
    "Libra": "Venus", "Scorpio": "Mars", "Sagittarius": "Jupiter",
    "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter",
}

# Classical BPHS dignity tables
_EXALTATION: dict[str, str] = {
    "Sun": "Aries", "Moon": "Taurus", "Mars": "Capricorn",
    "Mercury": "Virgo", "Jupiter": "Cancer", "Venus": "Pisces", "Saturn": "Libra",
}
_DEBILITATION: dict[str, str] = {
    "Sun": "Libra", "Moon": "Scorpio", "Mars": "Cancer",
    "Mercury": "Pisces", "Jupiter": "Capricorn", "Venus": "Virgo", "Saturn": "Aries",
}
_OWN_SIGNS: dict[str, list[str]] = {
    "Sun": ["Leo"], "Moon": ["Cancer"], "Mars": ["Aries", "Scorpio"],
    "Mercury": ["Gemini", "Virgo"], "Jupiter": ["Sagittarius", "Pisces"],
    "Venus": ["Taurus", "Libra"], "Saturn": ["Capricorn", "Aquarius"],
}
_MOOLATRIKONA: dict[str, str] = {
    "Sun": "Leo", "Moon": "Taurus", "Mars": "Aries",
    "Mercury": "Virgo", "Jupiter": "Sagittarius", "Venus": "Libra", "Saturn": "Aquarius",
}
_FRIENDLY: dict[str, list[str]] = {
    "Sun": ["Moon", "Mars", "Jupiter"],
    "Moon": ["Sun", "Mercury"],
    "Mars": ["Sun", "Moon", "Jupiter"],
    "Mercury": ["Sun", "Venus"],
    "Jupiter": ["Sun", "Moon", "Mars"],
    "Venus": ["Mercury", "Saturn"],
    "Saturn": ["Mercury", "Venus"],
}
_ENEMY: dict[str, list[str]] = {
    "Sun": ["Venus", "Saturn"],
    "Moon": ["None"],
    "Mars": ["Mercury"],
    "Mercury": ["Moon"],
    "Jupiter": ["Mercury", "Venus"],
    "Venus": ["Sun", "Moon"],
    "Saturn": ["Sun", "Moon", "Mars"],
}


def longitude_to_sign_and_degree(longitude: float) -> tuple[str, float]:
    longitude = longitude % 360
    return SIGNS[int(longitude // 30)], longitude % 30


def longitude_to_nakshatra(longitude: float) -> str:
    longitude = longitude % 360
    return NAKSHATRAS[int(longitude / (360 / 27))]


def get_sign_lord(sign: str) -> str:
    return SIGN_LORDS.get(sign, "Unknown")


def get_planet_dignity(planet: str, sign: str) -> str:
    if planet in ("Rahu", "Ketu"):
        return "neutral"
    if _EXALTATION.get(planet) == sign:
        return "exalted"
    if _DEBILITATION.get(planet) == sign:
        return "debilitated"
    if sign == _MOOLATRIKONA.get(planet):
        return "moolatrikona"
    if sign in _OWN_SIGNS.get(planet, []):
        return "own sign"
    sign_lord = get_sign_lord(sign)
    if sign_lord in _FRIENDLY.get(planet, []):
        return "friendly"
    if sign_lord in _ENEMY.get(planet, []):
        return "enemy"
    return "neutral"


def make_place(name: str, lat: float, lon: float, tz_offset: float) -> drik.Place:
    return drik.Place(name, lat, lon, tz_offset)
