"""Build the self-contained dashboard.html from template.html + data.json.

Keeps the template (look) and this script (data) separate: the dashboard
can be rebuilt after every sync without anyone touching HTML.

Usage:
    python build_dashboard.py --local data.json --out dashboard.html
        # local file in, local file out - for previewing without Drive access

    python build_dashboard.py
        # reads data.json from the garmin/ Drive folder, uploads
        # dashboard.html back to the same folder
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TEMPLATE_PATH = Path(__file__).parent / "template.html"
PLACEHOLDER = "__GARMIN_DASHBOARD_DATA_JSON__"


def build_dashboard_html(data: dict) -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False)
    # A stray "</script" inside the JSON text would otherwise close the data
    # script tag early when the browser parses the HTML.
    payload = payload.replace("</script", "<\\/script")
    return template.replace(PLACEHOLDER, payload)


def _fetch_data_from_drive(access_token: str, folder_id: str) -> dict:
    from drive_writer import read_file

    raw = read_file(access_token, folder_id, "data.json")
    if raw is None:
        print("Keine data.json in Drive gefunden - erst einen Sync laufen lassen.", file=sys.stderr)
        sys.exit(1)
    return json.loads(raw)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

    parser = argparse.ArgumentParser()
    parser.add_argument("--local", help="Read data from this local JSON file instead of Drive")
    parser.add_argument("--out", help="Write HTML to this local file instead of uploading to Drive")
    args = parser.parse_args()

    if args.local:
        data = json.loads(Path(args.local).read_text(encoding="utf-8"))
    else:
        from gdrive_auth import get_access_token, get_garmin_folder_id

        access_token = get_access_token()
        folder_id = get_garmin_folder_id()
        data = _fetch_data_from_drive(access_token, folder_id)

    html = build_dashboard_html(data)

    if args.out:
        Path(args.out).write_text(html, encoding="utf-8")
        print(f"Dashboard geschrieben nach {args.out}")
    else:
        from drive_writer import write_file
        from gdrive_auth import get_access_token, get_garmin_folder_id

        access_token = get_access_token()
        folder_id = get_garmin_folder_id()
        write_file(access_token, folder_id, "dashboard.html", html, "text/html")
        print("dashboard.html nach Drive geschrieben")
