"""Google Drive login via the OAuth 2.0 device authorization grant.

Used because this session has no reachable browser redirect target: the
device flow instead shows the user a short code and a URL, they approve on
any device with a browser, and we poll Google's token endpoint until it
reports success. Only the drive.file scope is requested (access limited to
files/folders this app creates - never the user's whole Drive).

Usage:
    python gdrive_auth.py start   -> prints the code + URL, saves pending state
    python gdrive_auth.py finish  -> polls until the user approves, then
                                      stores the encrypted refresh token and
                                      creates the garmin/ folder in Drive
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests

from crypto_utils import SECRETS_DIR, decrypt_from_file, encrypt_to_file

CLIENT_SECRET_FILE = SECRETS_DIR / "google_client_secret.json"
PENDING_FILE = SECRETS_DIR / "google_device_pending.json"
TOKEN_FILE = SECRETS_DIR / "google_token.enc"
FOLDER_ID_FILE = SECRETS_DIR / "google_garmin_folder_id.txt"

SCOPE = "https://www.googleapis.com/auth/drive.file"
DEVICE_CODE_URL = "https://oauth2.googleapis.com/device/code"
TOKEN_URL = "https://oauth2.googleapis.com/token"
DRIVE_API = "https://www.googleapis.com/drive/v3"


def _load_client() -> tuple[str, str]:
    data = json.loads(CLIENT_SECRET_FILE.read_text())["installed"]
    return data["client_id"], data["client_secret"]


def start() -> None:
    client_id, _ = _load_client()
    resp = requests.post(
        DEVICE_CODE_URL,
        data={"client_id": client_id, "scope": SCOPE},
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()

    PENDING_FILE.write_text(json.dumps(payload))
    PENDING_FILE.chmod(0o600)

    print("=" * 60)
    print("GOOGLE DRIVE LOGIN")
    print("=" * 60)
    print(f"1. Oeffne im Browser: {payload['verification_url']}")
    print(f"2. Gib diesen Code ein: {payload['user_code']}")
    print(f"3. Melde dich an und bestaetige den Zugriff.")
    print(f"(Code laeuft ab in {payload['expires_in'] // 60} Minuten)")
    print("=" * 60)
    print("Danach: python gdrive_auth.py finish")


def finish() -> None:
    if not PENDING_FILE.exists():
        print("Kein offener Login. Erst 'start' ausfuehren.", file=sys.stderr)
        sys.exit(1)

    pending = json.loads(PENDING_FILE.read_text())
    client_id, client_secret = _load_client()
    interval = pending.get("interval", 5)
    deadline = time.time() + pending.get("expires_in", 1800)

    token_data = None
    while time.time() < deadline:
        resp = requests.post(
            TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "device_code": pending["device_code"],
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
            timeout=30,
        )
        body = resp.json()
        if resp.status_code == 200:
            token_data = body
            break
        error = body.get("error")
        if error == "authorization_pending":
            time.sleep(interval)
            continue
        if error == "slow_down":
            interval += 5
            time.sleep(interval)
            continue
        print(f"Login fehlgeschlagen: {error}", file=sys.stderr)
        sys.exit(1)

    if token_data is None:
        print("Zeitlimit erreicht, bitte 'start' erneut ausfuehren.", file=sys.stderr)
        sys.exit(1)

    encrypt_to_file(TOKEN_FILE, json.dumps(token_data))
    PENDING_FILE.unlink(missing_ok=True)
    print("Google-Login erfolgreich. Token verschluesselt gespeichert.")

    folder_id = ensure_garmin_folder(token_data["access_token"])
    FOLDER_ID_FILE.write_text(folder_id)
    FOLDER_ID_FILE.chmod(0o600)
    print(f"Drive-Ordner 'garmin/' bereit (id={folder_id})")


def ensure_garmin_folder(access_token: str) -> str:
    headers = {"Authorization": f"Bearer {access_token}"}
    query = (
        "name='garmin' and mimeType='application/vnd.google-apps.folder' "
        "and trashed=false"
    )
    resp = requests.get(
        f"{DRIVE_API}/files",
        headers=headers,
        params={"q": query, "fields": "files(id,name)"},
        timeout=30,
    )
    resp.raise_for_status()
    files = resp.json().get("files", [])
    if files:
        return files[0]["id"]

    resp = requests.post(
        f"{DRIVE_API}/files",
        headers=headers,
        json={"name": "garmin", "mimeType": "application/vnd.google-apps.folder"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    """Exchange a refresh token for a fresh access token. Pure - no file I/O -
    so callers that keep their credentials elsewhere (e.g. the Streamlit
    app's st.secrets) can reuse it without touching this session's local
    secrets/ files.
    """
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_access_token() -> str:
    """Return a valid access token using this session's local secrets/ files."""
    token_data = json.loads(decrypt_from_file(TOKEN_FILE))
    client_id, client_secret = _load_client()
    return refresh_access_token(client_id, client_secret, token_data["refresh_token"])


def get_garmin_folder_id() -> str:
    return FOLDER_ID_FILE.read_text().strip()


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("start", "finish"):
        print("Usage: python gdrive_auth.py [start|finish]", file=sys.stderr)
        sys.exit(1)
    {"start": start, "finish": finish}[sys.argv[1]]()
