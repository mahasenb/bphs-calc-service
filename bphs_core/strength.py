from dataclasses import dataclass
from .chart import ChartSnapshot, PlanetData
from . import utils

SHADBALA_MINIMUMS: dict[str, float] = {
    "Sun": 5.0, "Moon": 6.0, "Mars": 5.0,
    "Mercury": 7.0, "Jupiter": 6.5, "Venus": 5.5, "Saturn": 5.0,
}

# Directional strength (dig bala) peak houses
_DIG_BALA_PEAK: dict[str, int] = {
    "Sun": 10, "Mars": 10, "Jupiter": 1, "Mercury": 1,
    "Moon": 4, "Venus": 4, "Saturn": 7,
}

# Natural strength (naisargika bala) order — fixed values per BPHS
_NAISARGIKA: dict[str, float] = {
    "Sun": 60.0, "Moon": 51.43, "Venus": 42.86, "Jupiter": 34.29,
    "Mercury": 25.71, "Mars": 17.14, "Saturn": 8.57,
}

# BPHS exaltation degrees (tropical index for reference, sidereal approximation)
_EXALT_DEG: dict[str, float] = {
    "Sun": 10.0, "Moon": 33.0, "Mars": 298.0, "Mercury": 165.0,
    "Jupiter": 95.0, "Venus": 357.0, "Saturn": 200.0,
}


@dataclass
class ShadbalaResult:
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


@dataclass
class BhavabalaResult:
    house_number: int
    bala_total: float
    bhava_adhipathi_bala: float
    bhava_drik: float
    rank: str


def _sthana_bala(pd: PlanetData, planet: str) -> float:
    dignity = pd.dignity
    if dignity == "exalted":
        return 60.0
    if dignity == "moolatrikona":
        return 45.0
    if dignity == "own sign":
        return 30.0
    if dignity == "friendly":
        return 15.0
    if dignity == "neutral":
        return 7.5
    if dignity == "enemy":
        return 3.75
    if dignity == "debilitated":
        return 0.0
    return 7.5


def _dig_bala(pd: PlanetData, planet: str) -> float:
    peak = _DIG_BALA_PEAK.get(planet)
    if peak is None:
        return 0.0
    diff = abs(pd.house - peak)
    if diff > 6:
        diff = 12 - diff
    return max(0.0, 60.0 - diff * 10.0)


def _kaala_bala(snapshot: ChartSnapshot, planet: str) -> float:
    pd = snapshot.rasi_chart.get(planet)
    if pd is None:
        return 0.0
    # Simplified: day planets (Sun, Jupiter, Venus, Saturn) stronger during day;
    # moon sign determines day/night (Moon in 1-6 houses = day chart approx.)
    moon = snapshot.rasi_chart.get("Moon")
    is_day = moon and moon.house in range(7, 13)
    day_planets = {"Sun", "Jupiter", "Venus", "Saturn"}
    night_planets = {"Moon", "Mars", "Mercury"}
    if is_day and planet in day_planets:
        return 30.0
    if not is_day and planet in night_planets:
        return 30.0
    return 15.0


def _cheshta_bala(pd: PlanetData, planet: str) -> float:
    if planet in ("Sun", "Moon"):
        return 0.0
    return 30.0 if pd.is_retrograde else 15.0


def _drik_bala(snapshot: ChartSnapshot, planet: str) -> float:
    pd = snapshot.rasi_chart.get(planet)
    if pd is None:
        return 0.0
    score = 0.0
    for other_name, other_pd in snapshot.rasi_chart.items():
        if other_name == planet:
            continue
        if planet in other_pd.aspects:
            if other_name in ("Jupiter", "Venus", "Mercury"):
                score += 15.0
            elif other_name in ("Sun", "Moon", "Mars", "Saturn"):
                score -= 15.0
    return max(0.0, score)


def compute_shadbala(snapshot: ChartSnapshot, planet: str) -> ShadbalaResult:
    pd = snapshot.rasi_chart.get(planet)
    if pd is None:
        raise ValueError(f"Planet {planet} not found in chart")

    sthana = _sthana_bala(pd, planet)
    dig = _dig_bala(pd, planet)
    kaala = _kaala_bala(snapshot, planet)
    cheshta = _cheshta_bala(pd, planet)
    naisargika = _NAISARGIKA.get(planet, 0.0)
    drik = _drik_bala(snapshot, planet)
    total = sthana + dig + kaala + cheshta + naisargika + drik
    minimum = SHADBALA_MINIMUMS.get(planet, 5.0)

    # Convert from raw units to rupas (divide by 60 per BPHS convention)
    total_rupas = round(total / 60.0, 3)
    minimum_rupas = minimum

    return ShadbalaResult(
        planet=planet,
        sthana_bala=round(sthana / 60, 3),
        dig_bala=round(dig / 60, 3),
        kaala_bala=round(kaala / 60, 3),
        cheshta_bala=round(cheshta / 60, 3),
        naisargika_bala=round(naisargika / 60, 3),
        drik_bala=round(drik / 60, 3),
        total_bala=total_rupas,
        minimum_bala=minimum_rupas,
        is_below_minimum=total_rupas < minimum_rupas,
    )


def _bhava_adhipathi_bala(snapshot: ChartSnapshot, house: int) -> float:
    sign = utils.SIGNS[(int(snapshot.house_cusps[house - 1] // 30)) % 12]
    lord = utils.get_sign_lord(sign)
    lord_pd = snapshot.rasi_chart.get(lord)
    if lord_pd is None:
        return 0.0
    result = compute_shadbala(snapshot, lord)
    return result.total_bala


def _bhava_drik_bala(snapshot: ChartSnapshot, house: int) -> float:
    score = 0.0
    for name, pd in snapshot.rasi_chart.items():
        if pd.house == house:
            if name in ("Jupiter", "Venus", "Mercury"):
                score += 10.0
            elif name in ("Mars", "Saturn", "Sun"):
                score -= 10.0
    return score


def compute_bhavabala(snapshot: ChartSnapshot, house: int) -> BhavabalaResult:
    adhipathi = _bhava_adhipathi_bala(snapshot, house)
    drik = _bhava_drik_bala(snapshot, house)
    total = round(adhipathi + max(0.0, drik), 3)
    return BhavabalaResult(
        house_number=house,
        bala_total=total,
        bhava_adhipathi_bala=round(adhipathi, 3),
        bhava_drik=round(drik, 3),
        rank="",  # rank assigned after all 12 computed
    )


def compute_all_bhavabala(snapshot: ChartSnapshot) -> list[BhavabalaResult]:
    results = [compute_bhavabala(snapshot, h) for h in range(1, 13)]
    totals = [r.bala_total for r in results]
    q1 = sorted(totals)[3]
    q3 = sorted(totals)[8]
    for r in results:
        if r.bala_total >= q3:
            r.rank = "strong"
        elif r.bala_total <= q1:
            r.rank = "weak"
        else:
            r.rank = "average"
    return results


def compute_ashtakavarga(snapshot: ChartSnapshot,
                         planet: str | None = None) -> dict:
    """
    Simplified Ashtakavarga: each planet contributes 1 point to each sign
    based on classical benefic positions from each of the 8 reference points
    (7 planets + lagna). Full table per BPHS chapter 66.
    Returns binna (individual) and samudaya (aggregate) scores per sign.
    """
    signs = utils.SIGNS
    # benefic sign offsets from each planet's position (1-based house offsets)
    BENEFIC_OFFSETS = {
        "Sun":     [1, 2, 4, 7, 8, 9, 10, 11],
        "Moon":    [3, 6, 10, 11],
        "Mars":    [1, 2, 4, 7, 8, 10, 11],
        "Mercury": [1, 3, 5, 6, 9, 10, 11, 12],
        "Jupiter": [1, 2, 3, 4, 7, 8, 10, 11],
        "Venus":   [1, 2, 3, 4, 5, 8, 9, 11, 12],
        "Saturn":  [3, 5, 6, 11],
        "Lagna":   [3, 6, 10, 11],
    }

    planet_signs: dict[str, int] = {
        name: utils.SIGNS.index(pd.sign)
        for name, pd in snapshot.rasi_chart.items()
    }
    lagna_idx = utils.SIGNS.index(snapshot.lagna)

    binna: dict[str, dict[str, int]] = {}
    samudaya = [0] * 12

    ref_planets = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
    for ref in ref_planets:
        ref_idx = planet_signs.get(ref, 0)
        offsets = BENEFIC_OFFSETS.get(ref, [])
        scores = [0] * 12
        for offset in offsets:
            target = (ref_idx + offset - 1) % 12
            scores[target] = 1
        binna[ref] = {signs[i]: scores[i] for i in range(12)}
        for i in range(12):
            samudaya[i] += scores[i]

    # Lagna contribution
    lagna_offsets = BENEFIC_OFFSETS["Lagna"]
    lagna_scores = [0] * 12
    for offset in lagna_offsets:
        target = (lagna_idx + offset - 1) % 12
        lagna_scores[target] = 1
    binna["Lagna"] = {signs[i]: lagna_scores[i] for i in range(12)}
    for i in range(12):
        samudaya[i] += lagna_scores[i]

    sav = {signs[i]: samudaya[i] for i in range(12)}

    if planet is not None:
        return {"binna": binna.get(planet, {}), "samudaya": sav}
    return {"binna": binna, "samudaya": sav}
