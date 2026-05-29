from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Optional
import swisseph as swe
from jhora.panchanga import drik
from jhora.horoscope.chart import charts
from . import utils  # sets ephemeris path and Lahiri mode on import


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
    is_combust: bool = False
    combust_proximity_degrees: Optional[float] = None


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


# Combustion (astangata) orbs in degrees from the Sun (BPHS). Mercury and Venus
# take a tighter orb when retrograde. Sun (source) and the shadow planets
# Rahu/Ketu are never combust.
_COMBUSTION_ORB = {
    "Moon": 12.0, "Mars": 17.0, "Mercury": 14.0,
    "Jupiter": 11.0, "Venus": 10.0, "Saturn": 15.0,
}
_COMBUSTION_ORB_RETRO = {"Mercury": 12.0, "Venus": 8.0}


def _apply_combustion(rasi: dict[str, "PlanetData"], longitudes: dict[str, float]) -> None:
    """Flag planets within the Sun's combustion orb. Mutates PlanetData in place."""
    sun_lon = longitudes.get("Sun")
    if sun_lon is None:
        return
    for name, pd in rasi.items():
        orb = _COMBUSTION_ORB.get(name)
        if orb is None:
            continue
        if pd.is_retrograde and name in _COMBUSTION_ORB_RETRO:
            orb = _COMBUSTION_ORB_RETRO[name]
        diff = abs(longitudes[name] - sun_lon) % 360.0
        sep = min(diff, 360.0 - diff)
        if sep <= orb:
            pd.is_combust = True
            pd.combust_proximity_degrees = round(sep, 4)


def _build_varga_chart(varga_positions, retro_planets) -> dict[str, PlanetData]:
    # varga_positions[0] is the ascendant's position in this varga; the varga
    # lagna sign anchors house counting within the divisional chart. Without
    # this, house is meaningless (it was previously hardcoded to 1).
    varga_lagna_sign_idx = varga_positions[0][1][0]
    chart: dict[str, PlanetData] = {}
    for pid, (sign_idx, deg) in varga_positions[1:]:
        name = utils.PLANETS[pid]
        sign = utils.SIGNS[sign_idx]
        nakshatra = utils.longitude_to_nakshatra(sign_idx * 30 + deg)
        dignity = utils.get_planet_dignity(name, sign)
        is_retro = pid in retro_planets
        house = (sign_idx - varga_lagna_sign_idx) % 12 + 1

        chart[name] = PlanetData(
            planet=name, sign=sign, degrees=round(deg, 4),
            nakshatra=nakshatra, dignity=dignity, house=house,
            conjunctions=[], aspects=[], is_retrograde=is_retro,
        )
    return chart


class Chart:
    def __init__(self, person: PersonalData):
        self.person = person
        self._snapshot: Optional[ChartSnapshot] = None
        self._compute()

    def _compute(self):
        drik.set_ayanamsa_mode('LAHIRI')
        jd = _jd_from_person(self.person)
        place = utils.make_place(self.person.name, self.person.latitude, self.person.longitude, self.person.timezone_offset_hours)
        ayanamsa = drik.get_ayanamsa_value(jd)

        # House cusps using swisseph directly as in original codebase
        try:
            cusps, ascmc = swe.houses(jd, self.person.latitude, self.person.longitude, b"P")
        except Exception:
            cusps, ascmc = swe.houses(jd, self.person.latitude, self.person.longitude, b"E")

        # Adjust cusps to sidereal
        sid_cusps = [((c - ayanamsa) % 360) for c in cusps]

        # Calculate all divisional charts via pyjhora
        rasi_positions = charts.rasi_chart(jd, place)
        retro_planets = drik.planets_in_retrograde(jd, place)

        lagna_sign_index, _ = rasi_positions[0][1]
        lagna_sign = utils.SIGNS[lagna_sign_index]

        # Build Rasi Chart with conjunctions and aspects
        rasi = {}
        longitudes: dict[str, float] = {}
        for pid, (sign_idx, deg) in rasi_positions[1:]:
            name = utils.PLANETS[pid]
            sign = utils.SIGNS[sign_idx]
            nakshatra = utils.longitude_to_nakshatra(sign_idx * 30 + deg)
            dignity = utils.get_planet_dignity(name, sign)
            is_retro = pid in retro_planets
            final_lon = sign_idx * 30.0 + deg
            house = _compute_house(final_lon, sid_cusps)
            longitudes[name] = final_lon

            rasi[name] = PlanetData(
                planet=name, sign=sign, degrees=round(deg, 4),
                nakshatra=nakshatra, dignity=dignity, house=house,
                conjunctions=[], aspects=[], is_retrograde=is_retro,
            )

        for name, pd in rasi.items():
            pd.conjunctions = _find_conjunctions(name, pd.house, rasi)
            pd.aspects = _find_aspects(name, pd.house, rasi)

        _apply_combustion(rasi, longitudes)

        # Build other divisional charts using standardized vargas
        self._snapshot = ChartSnapshot(
            person=self.person,
            rasi_chart=rasi,
            hora_chart=_build_varga_chart(charts.hora_chart(rasi_positions), retro_planets),
            drekkana_chart=_build_varga_chart(charts.drekkana_chart(rasi_positions), retro_planets),
            navamsa_chart=_build_varga_chart(charts.navamsa_chart(rasi_positions), retro_planets),
            decamsa_chart=_build_varga_chart(charts.dasamsa_chart(rasi_positions), retro_planets),
            dwadasamsa_chart=_build_varga_chart(charts.dwadasamsa_chart(rasi_positions), retro_planets),
            chaturvimsa_chart=_build_varga_chart(charts.chaturvimsamsa_chart(rasi_positions), retro_planets),
            trimshamsa_chart=_build_varga_chart(charts.trimsamsa_chart(rasi_positions), retro_planets),
            saptamsa_chart=_build_varga_chart(charts.saptamsa_chart(rasi_positions), retro_planets),
            shashtyamsa_chart=_build_varga_chart(charts.shashtyamsa_chart(rasi_positions), retro_planets),
            lagna=lagna_sign,
            lagna_lord=utils.get_sign_lord(lagna_sign),
            ayanamsa_value=round(ayanamsa, 6),
            house_cusps=sid_cusps,
            jd=jd,
        )

    def snapshot(self) -> ChartSnapshot:
        return self._snapshot
