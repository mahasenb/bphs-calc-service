from dataclasses import dataclass
from datetime import datetime
import swisseph as swe
from jhora.panchanga import drik
from .chart import ChartSnapshot
from . import utils

_PYJHORA_TRANSIT_PLANETS = {
    "Sun": 0, "Moon": 1, "Mars": 2, "Mercury": 3,
    "Jupiter": 4, "Venus": 5, "Saturn": 6, "Rahu": 7,
}


@dataclass
class TransitPlacement:
    planet: str
    sign: str
    degrees: float
    nakshatra: str


@dataclass
class SadeSatiInfo:
    is_active: bool
    phase: str
    start_date: datetime
    end_date: datetime


def _transit_longitude(jd: float, planet_id: int) -> float:
    drik.set_ayanamsa_mode('LAHIRI')
    return drik.sidereal_longitude(jd, planet_id)


def _jd_from_date(dt: datetime) -> float:
    return swe.julday(dt.year, dt.month, dt.day,
                      dt.hour + dt.minute / 60 + dt.second / 3600)


def get_current_transits(snapshot: ChartSnapshot, at: datetime) -> dict:
    jd = _jd_from_date(at)
    result: dict[str, TransitPlacement] = {}
    for name, pid in _PYJHORA_TRANSIT_PLANETS.items():
        lon = _transit_longitude(jd, pid)
        sign, deg = utils.longitude_to_sign_and_degree(lon)
        nakshatra = utils.longitude_to_nakshatra(lon)
        result[name] = TransitPlacement(
            planet=name, sign=sign, degrees=round(deg, 4), nakshatra=nakshatra,
        )
    # Ketu is always exactly 180° from Rahu
    rahu_lon = _transit_longitude(jd, 7)
    ketu_lon = (rahu_lon + 180) % 360
    ketu_sign, ketu_deg = utils.longitude_to_sign_and_degree(ketu_lon)
    result["Ketu"] = TransitPlacement(
        planet="Ketu", sign=ketu_sign, degrees=round(ketu_deg, 4),
        nakshatra=utils.longitude_to_nakshatra(ketu_lon),
    )
    return result


def get_sade_sati_info(snapshot: ChartSnapshot, at: datetime) -> SadeSatiInfo:
    moon = snapshot.rasi_chart.get("Moon")
    if moon is None:
        return SadeSatiInfo(False, "none", at, at)

    moon_sign_idx = utils.SIGNS.index(moon.sign)
    jd = _jd_from_date(at)
    saturn_lon = _transit_longitude(jd, 6)  # Saturn ID is 6 in pyjhora
    saturn_sign_idx = int(saturn_lon // 30) % 12

    diff = (saturn_sign_idx - moon_sign_idx) % 12
    if diff == 11:
        phase = "first"
    elif diff == 0:
        phase = "second"
    elif diff == 1:
        phase = "third"
    else:
        return SadeSatiInfo(False, "none", at, at)

    # Approximate start/end: Saturn spends ~2.46 years per sign (29.46yr / 12)
    phase_offset = {"first": -1, "second": 0, "third": 1}[phase]
    target_sign_idx = (moon_sign_idx + phase_offset) % 12

    # Find ingress and egress for that sign (search ±4 years)
    from datetime import timedelta
    start_est = at - timedelta(days=2.5 * 365)
    end_est = at + timedelta(days=2.5 * 365)

    def saturn_in_sign(dt: datetime) -> bool:
        j = _jd_from_date(dt)
        lon = _transit_longitude(j, 6)
        return int(lon // 30) % 12 == target_sign_idx

    # Binary search for ingress
    lo, hi = start_est, at
    for _ in range(30):
        mid = lo + (hi - lo) / 2
        if saturn_in_sign(mid):
            hi = mid
        else:
            lo = mid
    ingress = hi

    # Binary search for egress
    lo, hi = at, end_est
    for _ in range(30):
        mid = lo + (hi - lo) / 2
        if saturn_in_sign(mid):
            lo = mid
        else:
            hi = mid
    egress = lo

    return SadeSatiInfo(is_active=True, phase=phase, start_date=ingress, end_date=egress)


def check_ashtakavarga_vedha(snapshot: ChartSnapshot,
                               planet: str, sign: str) -> bool:
    from .strength import compute_ashtakavarga
    akv = compute_ashtakavarga(snapshot, planet)
    binna = akv.get("binna", {})
    score = binna.get(sign, 0)
    return score < 4
