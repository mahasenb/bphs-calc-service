from dataclasses import dataclass
from .chart import ChartSnapshot
from . import utils


@dataclass
class SpecialPoint:
    name: str
    sign: str
    degrees: float
    description: str


def _sign_and_deg(lon: float) -> tuple[str, float]:
    return utils.longitude_to_sign_and_degree(lon % 360)


def get_arudha_lagna(snapshot: ChartSnapshot) -> SpecialPoint:
    """Arudha = 2 × lagna-lord-house − lagna house (counted from lagna)."""
    lagna_sign = snapshot.lagna
    lagna_idx = utils.SIGNS.index(lagna_sign)
    lord = snapshot.lagna_lord
    lord_pd = snapshot.rasi_chart.get(lord)
    if lord_pd is None:
        sign, deg = lagna_sign, 0.0
    else:
        lord_house = lord_pd.house
        arudha_house = ((2 * lord_house - 1) - 1) % 12 + 1
        if arudha_house == lord_house:
            arudha_house = ((arudha_house + 10 - 1) % 12) + 1
        if arudha_house == 1:
            arudha_house = 10
        arudha_sign_idx = (lagna_idx + arudha_house - 1) % 12
        sign = utils.SIGNS[arudha_sign_idx]
        deg = 0.0

    return SpecialPoint(
        name="Arudha Lagna",
        sign=sign,
        degrees=deg,
        description="Public image and material manifestation of the self",
    )


def get_upapada(snapshot: ChartSnapshot) -> SpecialPoint:
    """Upapada = Arudha of the 12th house (from 12th lord)."""
    lagna_idx = utils.SIGNS.index(snapshot.lagna)
    twelfth_sign_idx = (lagna_idx + 11) % 12
    twelfth_sign = utils.SIGNS[twelfth_sign_idx]
    twelfth_lord = utils.get_sign_lord(twelfth_sign)
    lord_pd = snapshot.rasi_chart.get(twelfth_lord)

    if lord_pd is None:
        sign = twelfth_sign
    else:
        lord_house_from_12th = ((lord_pd.house - 12) % 12) + 1
        upapada_house_from_12th = ((2 * lord_house_from_12th - 1) - 1) % 12 + 1
        upapada_sign_idx = (twelfth_sign_idx + upapada_house_from_12th - 1) % 12
        sign = utils.SIGNS[upapada_sign_idx]

    return SpecialPoint(
        name="Upapada Lagna",
        sign=sign,
        degrees=0.0,
        description="Nature of spouse and marriage",
    )


def get_atmakaraka(snapshot: ChartSnapshot) -> str:
    """Planet with highest degrees within its sign (excluding Rahu/Ketu)."""
    candidates = {p: d.degrees
                  for p, d in snapshot.rasi_chart.items()
                  if p not in ("Rahu", "Ketu")}
    if not candidates:
        return "Sun"
    return max(candidates, key=candidates.__getitem__)


def get_karakamsa(snapshot: ChartSnapshot) -> SpecialPoint:
    """Navamsa sign of the Atmakaraka."""
    ak = get_atmakaraka(snapshot)
    ak_navamsa = snapshot.navamsa_chart.get(ak)
    if ak_navamsa is None:
        sign = snapshot.lagna
    else:
        sign = ak_navamsa.sign

    return SpecialPoint(
        name="Karakamsa",
        sign=sign,
        degrees=0.0,
        description=f"Soul purpose — Atmakaraka ({ak}) in Navamsa",
    )
