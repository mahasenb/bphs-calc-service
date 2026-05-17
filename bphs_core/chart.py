from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Optional
import swisseph as swe
from . import utils  # sets ephemeris path on import


@dataclass
class PersonalData:
    name: str
    birth_date: datetime
    birth_time: time
    birth_place: str
    latitude: float
    longitude: float
    timezone_offset_hours: float


@dataclass
class PlanetData:
    planet: str
    sign: str
    degrees: float
    nakshatra: str
    dignity: str
    house: int
    conjunctions: list[str]
    aspects: list[str]
    is_retrograde: bool


@dataclass
class ChartSnapshot:
    person: PersonalData
    rasi_chart: dict[str, PlanetData]
    hora_chart: dict[str, PlanetData]          # D2
    drekkana_chart: dict[str, PlanetData]      # D3
    navamsa_chart: dict[str, PlanetData]       # D9
    decamsa_chart: dict[str, PlanetData]       # D10
    dwadasamsa_chart: dict[str, PlanetData]    # D12
    chaturvimsa_chart: dict[str, PlanetData]   # D24
    trimshamsa_chart: dict[str, PlanetData]    # D30
    saptamsa_chart: dict[str, PlanetData]      # D7
    shashtyamsa_chart: dict[str, PlanetData]   # D60
    lagna: str
    lagna_lord: str
    ayanamsa_value: float
    house_cusps: list[float] = field(default_factory=list)
    jd: float = 0.0


# Swiss Ephemeris planet IDs
_SWE_PLANETS = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS,
    "Mercury": swe.MERCURY, "Jupiter": swe.JUPITER,
    "Venus": swe.VENUS, "Saturn": swe.SATURN,
    "Rahu": swe.TRUE_NODE,
}

_VARGA_DIVISORS = {
    "navamsa": 9, "decamsa": 10, "dwadasamsa": 12,
    "chaturvimsa": 24, "trimshamsa": 30, "saptamsa": 7, "shashtyamsa": 60,
}

# Aspects each planet casts (house offsets, 1-based from its own house)
_ASPECTS = {
    "Sun": [7], "Moon": [7], "Mercury": [7], "Venus": [7],
    "Mars": [4, 7, 8], "Jupiter": [5, 7, 9], "Saturn": [3, 7, 10],
    "Rahu": [5, 7, 9], "Ketu": [5, 7, 9],
}


def _jd_from_person(p: PersonalData) -> float:
    naive = datetime.combine(p.birth_date, p.birth_time)
    utc_hour = (naive.hour + naive.minute / 60 + naive.second / 3600
                - p.timezone_offset_hours)
    return swe.julday(naive.year, naive.month, naive.day, utc_hour)


def _get_ayanamsa(jd: float) -> float:
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    return swe.get_ayanamsa_ut(jd)


def _sidereal_longitude(jd: float, planet_id: int) -> tuple[float, bool]:
    flags = swe.FLG_SIDEREAL | swe.FLG_SPEED
    result, _ = swe.calc_ut(jd, planet_id, flags)
    lon = result[0] % 360
    is_retro = result[3] < 0
    return lon, is_retro


def _ketu_longitude(rahu_lon: float) -> float:
    return (rahu_lon + 180) % 360


def _varga_longitude(tropical_lon: float, ayanamsa: float, divisor: int) -> float:
    sidereal = (tropical_lon - ayanamsa) % 360
    sign_idx = int(sidereal // 30)
    deg_in_sign = sidereal % 30
    varga_sign_offset = int(deg_in_sign / (30 / divisor))
    varga_sign = (sign_idx * divisor + varga_sign_offset) % 12
    return varga_sign * 30


def _hora_sign(sidereal: float) -> int:
    """D2 Hora — two 15° halves per sign. Odd signs: Sun(Leo)/Moon(Cancer); even: Moon/Sun.

    BPHS odd signs (Aries, Gemini, Leo …) are 0-indexed even (0,2,4,6,8,10).
    """
    sign_idx = int(sidereal // 30)
    in_first_half = (sidereal % 30) < 15
    if sign_idx % 2 == 0:               # BPHS odd sign
        return 4 if in_first_half else 3    # Leo=4, Cancer=3
    else:                               # BPHS even sign
        return 3 if in_first_half else 4


def _drekkana_sign(sidereal: float) -> int:
    """D3 Drekkana — triplicity-based (BPHS). Each 10° decan goes to the same-element sign.

    1st decan = same sign, 2nd = 5th from it (+4), 3rd = 9th from it (+8).
    """
    sign_idx = int(sidereal // 30)
    section = int((sidereal % 30) / 10)    # 0, 1, or 2
    offsets = (0, 4, 8)
    return (sign_idx + offsets[section]) % 12


def _build_special_varga_map(jd: float, ayanamsa: float,
                              sign_fn) -> dict[str, "PlanetData"]:
    """Build a varga planet map using a caller-supplied sign-index function.

    `sign_fn(sidereal_lon: float) -> int` must return a 0-indexed sign index.
    Houses are not meaningful in non-rasi vargas; all default to 1.
    """
    raw: dict[str, tuple[float, bool]] = {}
    for name, pid in _SWE_PLANETS.items():
        flags = swe.FLG_SIDEREAL | swe.FLG_SPEED
        result, _ = swe.calc_ut(jd, pid, flags)
        lon = result[0] % 360
        retro = result[3] < 0
        raw[name] = (lon, retro)

    rahu_lon = raw["Rahu"][0]
    raw["Ketu"] = (_ketu_longitude(rahu_lon), False)

    planets: dict[str, PlanetData] = {}
    for name, (sidereal_lon, retro) in raw.items():
        sign_idx = sign_fn(sidereal_lon)
        final_lon = sign_idx * 30.0
        sign, deg = utils.longitude_to_sign_and_degree(final_lon)
        nakshatra = utils.longitude_to_nakshatra(final_lon)
        dignity = utils.get_planet_dignity(name, sign)
        planets[name] = PlanetData(
            planet=name, sign=sign, degrees=round(deg, 4),
            nakshatra=nakshatra, dignity=dignity, house=1,
            conjunctions=[], aspects=[], is_retrograde=retro,
        )
    return planets


def _compute_house(lon: float, house_cusps: list[float]) -> int:
    for i in range(11, -1, -1):
        if _lon_gte(lon, house_cusps[i]):
            return i + 1
    return 1


def _lon_gte(lon: float, cusp: float) -> bool:
    return ((lon - cusp) % 360) < 180


def _find_conjunctions(planet: str, house: int,
                        all_planets: dict[str, "PlanetData"]) -> list[str]:
    return [p for p, d in all_planets.items()
            if p != planet and d.house == house]


def _find_aspects(planet: str, house: int,
                  all_planets: dict[str, "PlanetData"]) -> list[str]:
    aspected_houses = {((house - 1 + offset - 1) % 12) + 1
                       for offset in _ASPECTS.get(planet, [])}
    return [p for p, d in all_planets.items()
            if p != planet and d.house in aspected_houses]


def _build_planet_map(jd: float, ayanamsa: float,
                      house_cusps: list[float],
                      divisor: int = 1) -> dict[str, PlanetData]:
    raw: dict[str, tuple[float, bool]] = {}

    for name, pid in _SWE_PLANETS.items():
        flags = swe.FLG_SIDEREAL | swe.FLG_SPEED
        result, _ = swe.calc_ut(jd, pid, flags)
        lon = result[0] % 360
        retro = result[3] < 0
        raw[name] = (lon, retro)

    rahu_lon = raw["Rahu"][0]
    raw["Ketu"] = (_ketu_longitude(rahu_lon), False)

    planets: dict[str, PlanetData] = {}
    for name, (lon, retro) in raw.items():
        if divisor == 1:
            final_lon = lon
        else:
            # convert back to tropical, apply varga, then re-sidereal
            tropical_lon = (lon + ayanamsa) % 360
            final_lon = _varga_longitude(tropical_lon, ayanamsa, divisor)

        sign, deg = utils.longitude_to_sign_and_degree(final_lon)
        nakshatra = utils.longitude_to_nakshatra(final_lon)
        dignity = utils.get_planet_dignity(name, sign)
        house = _compute_house(final_lon, house_cusps) if divisor == 1 else 1

        planets[name] = PlanetData(
            planet=name, sign=sign, degrees=round(deg, 4),
            nakshatra=nakshatra, dignity=dignity, house=house,
            conjunctions=[], aspects=[], is_retrograde=retro,
        )

    # fill conjunctions and aspects (Rasi only — varga aspects are complex)
    if divisor == 1:
        for name, pd in planets.items():
            pd.conjunctions = _find_conjunctions(name, pd.house, planets)
            pd.aspects = _find_aspects(name, pd.house, planets)

    return planets


class Chart:
    def __init__(self, person: PersonalData):
        self.person = person
        self._snapshot: Optional[ChartSnapshot] = None
        self._compute()

    def _compute(self):
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        jd = _jd_from_person(self.person)
        ayanamsa = _get_ayanamsa(jd)

        # House cusps (Placidus; switch to equal if Placidus fails at extreme latitudes)
        try:
            cusps, ascmc = swe.houses(jd, self.person.latitude, self.person.longitude, b"P")
        except Exception:
            cusps, ascmc = swe.houses(jd, self.person.latitude, self.person.longitude, b"E")

        # Adjust cusps to sidereal
        sid_cusps = [((c - ayanamsa) % 360) for c in cusps]
        lagna_lon = (ascmc[0] - ayanamsa) % 360
        lagna_sign, _ = utils.longitude_to_sign_and_degree(lagna_lon)

        rasi = _build_planet_map(jd, ayanamsa, sid_cusps, 1)

        self._snapshot = ChartSnapshot(
            person=self.person,
            rasi_chart=rasi,
            hora_chart=_build_special_varga_map(jd, ayanamsa, _hora_sign),
            drekkana_chart=_build_special_varga_map(jd, ayanamsa, _drekkana_sign),
            navamsa_chart=_build_planet_map(jd, ayanamsa, sid_cusps, 9),
            decamsa_chart=_build_planet_map(jd, ayanamsa, sid_cusps, 10),
            dwadasamsa_chart=_build_planet_map(jd, ayanamsa, sid_cusps, 12),
            chaturvimsa_chart=_build_planet_map(jd, ayanamsa, sid_cusps, 24),
            trimshamsa_chart=_build_planet_map(jd, ayanamsa, sid_cusps, 30),
            saptamsa_chart=_build_planet_map(jd, ayanamsa, sid_cusps, 7),
            shashtyamsa_chart=_build_planet_map(jd, ayanamsa, sid_cusps, 60),
            lagna=lagna_sign,
            lagna_lord=utils.get_sign_lord(lagna_sign),
            ayanamsa_value=round(ayanamsa, 6),
            house_cusps=sid_cusps,
            jd=jd,
        )

    def snapshot(self) -> ChartSnapshot:
        return self._snapshot
