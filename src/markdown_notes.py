"""Render one Markdown note per day and per workout, in plain German."""

from __future__ import annotations

from drive_writer import fmt


def _seconds_to_hm(seconds) -> str:
    if seconds is None:
        return fmt(None)
    h, rem = divmod(int(seconds), 3600)
    m = rem // 60
    return f"{h} h {m} min"


def render_daily_note(metrics: dict) -> str:
    date = metrics["date"]
    sleep = metrics.get("sleep") or {}
    hrv = metrics.get("hrv") or {}
    battery = metrics.get("body_battery") or {}
    stress = metrics.get("stress") or {}
    readiness = metrics.get("training_readiness") or {}

    lines = [
        f"# Tageswerte {date}",
        "",
        "## Erholung",
        f"- Schlaf gesamt: {_seconds_to_hm(sleep.get('total_seconds'))}",
        f"- Schlaf-Score: {fmt(sleep.get('sleep_score'))}",
        f"- HRV (letzte Nacht): {fmt(hrv.get('last_night_avg'), ' ms')}",
        f"- HRV-Status: {fmt(hrv.get('status'))}",
        f"- Ruheherzfrequenz: {fmt(metrics.get('resting_hr'), ' bpm')}",
        f"- Body Battery: {fmt(battery.get('low'))} - {fmt(battery.get('high'))}",
        f"- Stress (Durchschnitt): {fmt(stress.get('avg'))}",
        f"- Schritte: {fmt(metrics.get('steps'))}",
        "",
        "## Training Readiness",
        f"- Score: {fmt(readiness.get('score'))}",
        f"- Einordnung: {fmt(readiness.get('level'))}",
    ]
    if readiness.get("feedback"):
        lines += ["", f"> {readiness['feedback']}"]
    return "\n".join(lines) + "\n"


def render_workout_note(activity: dict) -> str:
    name = activity.get("name") or "Training"
    date = (activity.get("start_time_local") or "")[:10]

    pace = activity.get("pace_min_per_km")
    if pace:
        pace_str = f"{int(pace)}:{round((pace % 1) * 60):02d} min/km"
    else:
        pace_str = fmt(None)

    lines = [
        f"# {name} — {date}",
        "",
        f"- Typ: {fmt(activity.get('type'))}",
        f"- Distanz: {fmt(activity.get('distance_km'), ' km', 2)}",
        f"- Dauer: {_seconds_to_hm(activity.get('duration_seconds'))}",
        f"- Pace: {pace_str}",
        f"- Ø Herzfrequenz: {fmt(activity.get('avg_hr'), ' bpm')}",
        f"- Max. Herzfrequenz: {fmt(activity.get('max_hr'), ' bpm')}",
        f"- Aerober Trainingseffekt: {fmt(activity.get('aerobic_training_effect'))}",
        f"- Anaerober Trainingseffekt: {fmt(activity.get('anaerobic_training_effect'))}",
        f"- Kalorien: {fmt(activity.get('calories'), ' kcal')}",
    ]
    return "\n".join(lines) + "\n"
