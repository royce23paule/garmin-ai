"""Safe per-field fetchers for Garmin daily metrics and activities.

Every single value is fetched independently and wrapped so one missing or
failing field (a day with no sleep data, a metric Garmin hasn't computed
yet, a transient API hiccup) never aborts the whole sync run. A missing
value is represented as None throughout - callers decide how to render
that ("keine Daten" in Markdown, a gap in a chart, never a 0).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("garmin_fetch")


def _safe(label: str, fn, *args) -> Any:
    try:
        return fn(*args)
    except Exception as e:  # noqa: BLE001 - one bad field must never abort the run
        logger.warning("Feld '%s' konnte nicht geladen werden: %s", label, e)
        return None


def fetch_daily_metrics(garmin, date_str: str) -> dict[str, Any]:
    """Fetch every daily wellness metric for one date (YYYY-MM-DD).

    Each key is fetched and reduced to a small, dashboard-friendly shape
    independently, so a failure in one never blocks the others.
    """
    sleep_raw = _safe("schlaf", garmin.get_sleep_data, date_str)
    hrv_raw = _safe("hrv", garmin.get_hrv_data, date_str)
    rhr_raw = _safe("ruhepuls", garmin.get_rhr_day, date_str)
    battery_raw = _safe("body_battery", garmin.get_body_battery, date_str, date_str)
    stress_raw = _safe("stress", garmin.get_all_day_stress, date_str)
    steps_raw = _safe("schritte", garmin.get_steps_data, date_str)
    readiness_raw = _safe("training_readiness", garmin.get_training_readiness, date_str)

    return {
        "date": date_str,
        "sleep": _extract_sleep(sleep_raw),
        "hrv": _extract_hrv(hrv_raw),
        "resting_hr": _extract_resting_hr(rhr_raw),
        "body_battery": _extract_body_battery(battery_raw),
        "stress": _extract_stress(stress_raw),
        "steps": _extract_steps(steps_raw),
        "training_readiness": _extract_training_readiness(readiness_raw),
    }


def _extract_sleep(raw: Any) -> dict[str, Any] | None:
    if not raw:
        return None
    dto = raw.get("dailySleepDTO") if isinstance(raw, dict) else None
    if not dto or dto.get("sleepTimeSeconds") is None:
        return None
    return {
        "total_seconds": dto.get("sleepTimeSeconds"),
        "deep_seconds": dto.get("deepSleepSeconds"),
        "light_seconds": dto.get("lightSleepSeconds"),
        "rem_seconds": dto.get("remSleepSeconds"),
        "awake_seconds": dto.get("awakeSleepSeconds"),
        "sleep_score": (dto.get("sleepScores") or {}).get("overall", {}).get("value"),
    }


def _extract_hrv(raw: Any) -> dict[str, Any] | None:
    if not raw:
        return None
    summary = raw.get("hrvSummary") if isinstance(raw, dict) else None
    if not summary or summary.get("lastNightAvg") is None:
        return None
    return {
        "last_night_avg": summary.get("lastNightAvg"),
        "weekly_avg": summary.get("weeklyAvg"),
        "status": summary.get("status"),
    }


def _extract_resting_hr(raw: Any) -> int | None:
    if not raw:
        return None
    try:
        stats = raw["allMetrics"]["metricsMap"]["WELLNESS_RESTING_HEART_RATE"]
        value = stats[0].get("value") if stats else None
        return int(value) if value is not None else None
    except (KeyError, IndexError, TypeError):
        return None


def _extract_body_battery(raw: Any) -> dict[str, Any] | None:
    if not raw or not isinstance(raw, list):
        return None
    day = raw[0]
    values = [v[1] for v in (day.get("bodyBatteryValuesArray") or []) if v and v[1] is not None]
    if not values:
        return None
    return {
        "low": min(values),
        "high": max(values),
        "charged": day.get("charged"),
        "drained": day.get("drained"),
    }


def _extract_stress(raw: Any) -> dict[str, Any] | None:
    if not raw:
        return None
    avg = raw.get("avgStressLevel")
    if avg is None or avg < 0:
        return None
    return {"avg": avg, "max": raw.get("maxStressLevel")}


def _extract_steps(raw: Any) -> int | None:
    if not raw or not isinstance(raw, list):
        return None
    total = sum(entry.get("steps", 0) or 0 for entry in raw)
    return total or None


def _extract_training_readiness(raw: Any) -> dict[str, Any] | None:
    if not raw or not isinstance(raw, list) or not raw[0]:
        return None
    entry = raw[0]
    score = entry.get("score")
    if score is None:
        return None
    return {"score": score, "level": entry.get("level"), "feedback": entry.get("feedbackLong")}


def fetch_activities(garmin, start_date: str, end_date: str) -> list[dict[str, Any]]:
    """Fetch activity summaries between two dates (YYYY-MM-DD, inclusive)."""
    raw_list = _safe("aktivitaeten", garmin.get_activities_by_date, start_date, end_date)
    if not raw_list:
        return []

    activities = []
    for raw in raw_list:
        activity = _extract_activity(raw)
        if activity is not None:
            activities.append(activity)
    return activities


def _extract_activity(raw: dict[str, Any]) -> dict[str, Any] | None:
    try:
        activity_id = raw["activityId"]
    except (KeyError, TypeError):
        return None

    distance_m = raw.get("distance")
    duration_s = raw.get("duration")
    pace_min_per_km = None
    if distance_m and duration_s and distance_m > 0:
        pace_min_per_km = (duration_s / 60) / (distance_m / 1000)

    return {
        "activity_id": activity_id,
        "name": raw.get("activityName") or "Training",
        "type": (raw.get("activityType") or {}).get("typeKey"),
        "start_time_local": raw.get("startTimeLocal"),
        "distance_km": (distance_m / 1000) if distance_m else None,
        "duration_seconds": duration_s,
        "pace_min_per_km": pace_min_per_km,
        "avg_hr": raw.get("averageHR"),
        "max_hr": raw.get("maxHR"),
        "aerobic_training_effect": raw.get("aerobicTrainingEffect"),
        "anaerobic_training_effect": raw.get("anaerobicTrainingEffect"),
        "calories": raw.get("calories"),
    }
