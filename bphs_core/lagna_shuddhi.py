"""
Lagna Shuddhi: minute-resolution electional muhurat.

Scans candidate windows to find the precise instant where the rising lagna
and its lord are well-disposed for the intended activity, clear of hard
inauspicious periods (Rahu Kala, Yamaganda, Gulika).

Does NOT compute or guess planetary positions — all astrology math uses
pyswisseph/pyjhora calls at the exact Julian Day of each candidate minute.
"""
from datetime import datetime, date as date_type
from typing import Literal

import swisseph as swe
from jhora.panchanga import drik

from . import utils
from .muhurat import compute_muhurat_for_day

# Chaldean descending-speed order (used for hora lord sequence)
_CHALDEAN = ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"]
_WEEKDAY_LORDS = {
    "Monday": "Moon", "Tuesday": "Mars", "Wednesday": "Mercury",
    "Thursday": "Jupiter", "Friday": "Venus", "Saturday": "Saturn", "Sunday": "Sun",
}
# pyjhora planet IDs (matches utils.PLANETS order)
_PLANET_IDS = {p: i for i, p in enumerate(utils.PLANETS)}
_MALEFIC_IDS = [
    _PLANET_IDS["Sun"], _PLANET_IDS["Mars"], _PLANET_IDS["Saturn"],
    _PLANET_IDS["Rahu"], _PLANET_IDS["Ketu"],
]
_FAVORABLE_CHOGADIYA = {
    "Chara (Auspicious)", "Labh (Auspicious)",
    "Amrit (Highly Auspicious)", "Shubh (Auspicious)",
}
_FAVORABLE_HORA = {"Sun", "Moon", "Mercury", "Jupiter", "Venus"}

ActivityCategory = Literal["generic", "business", "marriage", "travel", "surgery"]


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def _hhmm_to_mins(hhmm: str) -> int:
    return int(hhmm[:2]) * 60 + int(hhmm[3:5])


def _mins_to_hhmm(mins: int) -> str:
    mins = mins % (24 * 60)
    return f"{mins // 60:02d}:{mins % 60:02d}"


def _in_window(time_mins: int, start_hhmm: str, end_hhmm: str) -> bool:
    s = _hhmm_to_mins(start_hhmm)
    e = _hhmm_to_mins(end_hhmm)
    if e > s:
        return s <= time_mins < e
    # spans midnight
    return time_mins >= s or time_mins < e


def _label_at(time_mins: int, windows: list[dict]) -> str | None:
    for w in windows:
        if _in_window(time_mins, w["start"], w["end"]):
            return w.get("label")
    return None


def _jd_for_local(date_str: str, time_mins: int, tz_offset: float) -> float:
    d = datetime.strptime(date_str, "%Y-%m-%d")
    local_h = time_mins / 60.0
    utc_h = local_h - tz_offset
    return swe.julday(d.year, d.month, d.day, utc_h)


# ---------------------------------------------------------------------------
# Hora lord
# ---------------------------------------------------------------------------

def compute_hora_lord(date_str: str, time_hhmm: str, sunrise_hhmm: str) -> str:
    """Return the planetary hora lord at the given local time on the given date."""
    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    day_lord = _WEEKDAY_LORDS[date_obj.strftime("%A")]
    day_lord_idx = _CHALDEAN.index(day_lord)
    elapsed_mins = (_hhmm_to_mins(time_hhmm) - _hhmm_to_mins(sunrise_hhmm)) % (24 * 60)
    hora_num = elapsed_mins // 60
    return _CHALDEAN[(day_lord_idx + hora_num) % 7]


# ---------------------------------------------------------------------------
# Lagna at a specific JD
# ---------------------------------------------------------------------------

def compute_lagna_at_jd(jd: float, lat: float, lon: float) -> tuple[str, str]:
    """Return (lagna_sign, lagna_lord) for the given Julian Day (UT)."""
    drik.set_ayanamsa_mode('LAHIRI')
    ayanamsa = drik.get_ayanamsa_value(jd)
    try:
        _, ascmc = swe.houses(jd, lat, lon, b"P")
    except Exception:
        _, ascmc = swe.houses(jd, lat, lon, b"E")
    sid_asc = (ascmc[0] - ayanamsa) % 360
    sign = utils.SIGNS[int(sid_asc // 30)]
    return sign, utils.get_sign_lord(sign)


# ---------------------------------------------------------------------------
# Per-minute scoring
# ---------------------------------------------------------------------------

def _score_instant(
    jd: float,
    lagna_sign: str,
    lagna_lord: str,
    day_data: dict,
    time_mins: int,
    activity: ActivityCategory,
) -> tuple[float, dict]:
    """
    Score a single candidate instant. Returns (score 0..1, detail_dict).
    score = 0.0 means hard-disqualified (Rahu Kala / Yamaganda / Gulika).
    """
    inauspicious = day_data.get("inauspicious_periods", [])
    in_rahu = any(
        "Rahu" in (w.get("label") or "") and _in_window(time_mins, w["start"], w["end"])
        for w in inauspicious
    )
    in_yama = any(
        "Yamagan" in (w.get("label") or "") and _in_window(time_mins, w["start"], w["end"])
        for w in inauspicious
    )
    in_guli = any(
        "Gulika" in (w.get("label") or "") and _in_window(time_mins, w["start"], w["end"])
        for w in inauspicious
    )
    in_durm = any(
        "Durmuhurt" in (w.get("label") or "") and _in_window(time_mins, w["start"], w["end"])
        for w in inauspicious
    )
    in_varj = any(
        "Varjyam" in (w.get("label") or "") and _in_window(time_mins, w["start"], w["end"])
        for w in inauspicious
    )

    detail = {
        "in_rahu_kala": in_rahu,
        "in_yamaganda": in_yama,
        "in_gulika": in_guli,
        "in_durmuhurtam": in_durm,
        "in_varjyam": in_varj,
        "in_auspicious_muhurta": None,
        "chogadiya_label": None,
        "hora_lord": "",
        "lagna_lord_house": 0,
        "lagna_lord_dignity": "unknown",
        "malefics_in_lagna": 0,
    }

    if in_rahu or in_yama or in_guli:
        return 0.0, detail

    if activity == "surgery" and (in_durm or in_varj):
        return 0.0, detail

    in_auspicious = _label_at(time_mins, day_data.get("auspicious_muhurtas", []))
    chogadiya_label = _label_at(time_mins, day_data.get("chogadiya", []))
    hora_lord = compute_hora_lord(
        day_data["date"], _mins_to_hhmm(time_mins), day_data["sunrise"]
    )

    # Lagna lord transit position at this exact instant
    lagna_sign_idx = utils.SIGNS.index(lagna_sign)
    lord_id = _PLANET_IDS.get(lagna_lord, -1)
    lord_house = 0
    lord_dignity = "neutral"
    if lord_id >= 0:
        try:
            lord_lon = drik.sidereal_longitude(jd, lord_id)
            lord_sign_idx = int(lord_lon // 30) % 12
            lord_house = (lord_sign_idx - lagna_sign_idx) % 12 + 1
            lord_dignity = utils.get_planet_dignity(lagna_lord, utils.SIGNS[lord_sign_idx])
        except Exception:
            pass

    # Malefics in lagna sign at this instant
    malefics_in_lagna = 0
    for pid in _MALEFIC_IDS:
        try:
            m_lon = drik.sidereal_longitude(jd, pid)
            if int(m_lon // 30) % 12 == lagna_sign_idx:
                malefics_in_lagna += 1
        except Exception:
            pass

    detail.update({
        "in_auspicious_muhurta": in_auspicious,
        "chogadiya_label": chogadiya_label,
        "hora_lord": hora_lord,
        "lagna_lord_house": lord_house,
        "lagna_lord_dignity": lord_dignity,
        "malefics_in_lagna": malefics_in_lagna,
    })

    # --- Base score ---
    score = 0.4

    if in_durm:
        score -= 0.12
    if in_varj:
        score -= 0.12

    # Lagna lord dignity
    dignity_bonus = {
        "exalted": 0.20, "moolatrikona": 0.15, "own sign": 0.15,
        "friendly": 0.08, "neutral": 0.0, "enemy": -0.08, "debilitated": -0.15,
    }.get(lord_dignity, 0.0)
    score += dignity_bonus

    # Lagna lord house (whole-sign from lagna)
    if lord_house in (1, 4, 7, 10):
        score += 0.15
    elif lord_house in (5, 9):
        score += 0.10
    elif lord_house in (2, 3, 11):
        score += 0.05
    elif lord_house in (6, 8, 12):
        score -= 0.15

    # In auspicious muhurta
    if in_auspicious:
        score += 0.12 if in_auspicious == "Abhijit Muhurta" else 0.08

    # Favorable chogadiya
    if chogadiya_label in _FAVORABLE_CHOGADIYA:
        cg_bonus = 0.15 if activity == "travel" else 0.08
        score += cg_bonus

    # Benefic hora lord
    if hora_lord in _FAVORABLE_HORA:
        score += 0.05

    # Malefics in lagna
    score -= min(malefics_in_lagna * 0.08, 0.16)

    # Activity-specific adjustments
    if activity == "marriage":
        score += dignity_bonus * 0.2  # amplify dignity weight
    elif activity == "business":
        if lord_house in (1, 4, 7, 10):
            score += 0.05  # extra kendra bonus

    return max(0.0, min(1.0, score)), detail


# ---------------------------------------------------------------------------
# Candidate window selection
# ---------------------------------------------------------------------------

def _candidate_minutes(day_data: dict) -> list[int]:
    """Return sorted list of minute-of-day values to scan for this day."""
    auspicious = day_data.get("auspicious_muhurtas", [])
    chogadiya = [
        w for w in day_data.get("chogadiya", [])
        if w.get("label") in _FAVORABLE_CHOGADIYA
    ]
    minutes: set[int] = set()
    for window_list in (auspicious, chogadiya):
        for w in window_list:
            s = _hhmm_to_mins(w["start"])
            e = _hhmm_to_mins(w["end"])
            if e <= s:
                e += 24 * 60
            for m in range(s, e):
                minutes.add(m % (24 * 60))
    return sorted(minutes)


# ---------------------------------------------------------------------------
# Main scan function
# ---------------------------------------------------------------------------

def scan_lagna_shuddhi(
    lat: float,
    lon: float,
    tz_offset: float,
    birth_nakshatra: str | None,
    birth_moon_sign: str | None,
    start_date: str,
    end_date: str,
    activity: ActivityCategory = "generic",
    step_seconds: int = 60,
) -> dict:
    """
    Scan all candidate auspicious windows across the date range at `step_seconds`
    resolution. Returns the best-scored instant + a tolerance band + top samples.

    Returns a dict with keys:
      best_instant, best_window, top_samples (list, up to 20 best)
    Each sample dict has all LagnaShuddhiSample fields.
    """
    place = utils.make_place("scan", lat, lon, tz_offset)
    step_mins = max(1, step_seconds // 60)

    start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
    end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
    from datetime import timedelta
    curr = start_dt

    all_samples: list[dict] = []

    while curr <= end_dt:
        day_data = compute_muhurat_for_day(
            place, curr, birth_nakshatra, birth_moon_sign
        )
        candidates = _candidate_minutes(day_data)
        if step_mins > 1:
            candidates = [m for i, m in enumerate(candidates) if i % step_mins == 0]

        for time_mins in candidates:
            jd = _jd_for_local(day_data["date"], time_mins, tz_offset)
            lagna_sign, lagna_lord = compute_lagna_at_jd(jd, lat, lon)
            score, detail = _score_instant(
                jd, lagna_sign, lagna_lord, day_data, time_mins, activity
            )
            all_samples.append({
                "instant": f"{day_data['date']} {_mins_to_hhmm(time_mins)}",
                "lagna_sign": lagna_sign,
                "lagna_lord": lagna_lord,
                "lagna_lord_house": detail["lagna_lord_house"],
                "lagna_lord_dignity": detail["lagna_lord_dignity"],
                "hora_lord": detail["hora_lord"],
                "chogadiya_label": detail["chogadiya_label"],
                "in_rahu_kala": detail["in_rahu_kala"],
                "in_yamaganda": detail["in_yamaganda"],
                "in_gulika": detail["in_gulika"],
                "in_durmuhurtam": detail["in_durmuhurtam"],
                "in_varjyam": detail["in_varjyam"],
                "in_auspicious_muhurta": detail["in_auspicious_muhurta"],
                "score": round(score, 4),
            })

        curr += timedelta(days=1)

    if not all_samples:
        # Fallback: no auspicious windows found — return a zero-scored placeholder
        return {
            "best_instant": None,
            "best_window": None,
            "top_samples": [],
        }

    # Sort by score descending
    ranked = sorted(all_samples, key=lambda s: s["score"], reverse=True)
    best = ranked[0]

    # Tolerance band: contiguous run of samples around best_instant where
    # score >= 0.85 * best_score and within ±5 minutes of best_instant
    best_date, best_time = best["instant"].split(" ")
    best_mins = _hhmm_to_mins(best_time)
    best_score = best["score"]
    threshold = 0.85 * best_score

    band_start = best_mins
    band_end = best_mins

    # Walk backwards
    for sample in sorted(all_samples, key=lambda s: s["instant"], reverse=True):
        s_date, s_time = sample["instant"].split(" ")
        if s_date != best_date:
            continue
        s_mins = _hhmm_to_mins(s_time)
        if s_mins > best_mins:
            continue
        if best_mins - s_mins > 5:
            break
        if sample["score"] >= threshold:
            band_start = min(band_start, s_mins)

    # Walk forwards
    for sample in sorted(all_samples, key=lambda s: s["instant"]):
        s_date, s_time = sample["instant"].split(" ")
        if s_date != best_date:
            continue
        s_mins = _hhmm_to_mins(s_time)
        if s_mins < best_mins:
            continue
        if s_mins - best_mins > 5:
            break
        if sample["score"] >= threshold:
            band_end = max(band_end, s_mins)

    best_window = {
        "start": _mins_to_hhmm(band_start),
        "end": _mins_to_hhmm(band_end + 1),
        "label": f"Best window for {activity}",
    }

    return {
        "best_instant": best,
        "best_window": best_window,
        "top_samples": ranked[:20],
    }
