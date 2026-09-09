"""Orchestrate one sync run: fetch N days of Garmin data, write Markdown
notes + data.json to the garmin/ Google Drive folder.

Usage:
    python sync.py --days 3 --dry-run   # fetch only, print a summary, write nothing
    python sync.py --days 60            # fetch and write everything to Drive
"""

from __future__ import annotations

import argparse
import datetime as dt
import json

from drive_writer import write_file, write_json
from garmin_client import get_client
from garmin_fetch import fetch_activities, fetch_daily_metrics
from markdown_notes import render_daily_note, render_workout_note


def _date_range(days: int) -> list[str]:
    today = dt.date.today()
    return [(today - dt.timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]


def run_sync(days: int, dry_run: bool) -> dict:
    garmin = get_client()
    dates = _date_range(days)

    daily_results = []
    for date_str in dates:
        metrics = fetch_daily_metrics(garmin, date_str)
        daily_results.append(metrics)
        if not dry_run:
            write_file(f"{date_str}.md", render_daily_note(metrics))

    activities = fetch_activities(garmin, dates[0], dates[-1])
    for activity in activities:
        if not dry_run:
            note_name = f"workout-{(activity['start_time_local'] or '')[:10]}-{activity['activity_id']}.md"
            write_file(note_name, render_workout_note(activity))

    data = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "range_days": days,
        "days": daily_results,
        "activities": activities,
    }
    if not dry_run:
        write_json("data.json", data)

    return data


def _summarize(data: dict) -> None:
    days_with_data = sum(
        1 for d in data["days"]
        if any(d.get(k) is not None for k in (
            "sleep", "hrv", "resting_hr", "body_battery", "stress", "steps", "training_readiness"
        ))
    )
    print(f"Zeitraum: {data['range_days']} Tage")
    print(f"Tage mit mindestens einem Wert: {days_with_data} / {len(data['days'])}")
    print(f"Aktivitaeten gefunden: {len(data['activities'])}")
    print()
    print(json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = run_sync(args.days, args.dry_run)
    _summarize(result)
