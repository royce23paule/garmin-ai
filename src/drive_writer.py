"""Create/read/update files inside the garmin/ Google Drive folder.

Uses the Drive v3 REST API directly via requests - consistent with
gdrive_auth.py, no need for the heavier googleapiclient wrapper for what
is just "find or create a file by name, then read/write its content".

access_token and folder_id are passed in explicitly (fetched once by the
caller) rather than looked up per call - a sync run writes many files and
refreshing the token or querying the folder id every time would be
wasteful and slow. This also lets the Streamlit app reuse the same
functions with credentials sourced from st.secrets instead of this
session's local secrets/ files.
"""

from __future__ import annotations

import json

import requests

from gdrive_auth import DRIVE_API

NO_DATA = "keine Daten"


def _find_file_id(access_token: str, name: str, parent_id: str) -> str | None:
    headers = {"Authorization": f"Bearer {access_token}"}
    query = f"name='{name}' and '{parent_id}' in parents and trashed=false"
    resp = requests.get(
        f"{DRIVE_API}/files",
        headers=headers,
        params={"q": query, "fields": "files(id,name)"},
        timeout=30,
    )
    resp.raise_for_status()
    files = resp.json().get("files", [])
    return files[0]["id"] if files else None


def read_file(access_token: str, folder_id: str, name: str) -> bytes | None:
    """Return the raw content of `name` inside the folder, or None if it doesn't exist."""
    file_id = _find_file_id(access_token, name, folder_id)
    if file_id is None:
        return None
    resp = requests.get(
        f"{DRIVE_API}/files/{file_id}",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"alt": "media"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.content


def write_file(
    access_token: str, folder_id: str, name: str, content: str, mime_type: str = "text/markdown"
) -> str:
    """Create or overwrite a file named `name` inside the folder. Returns its file id."""
    headers = {"Authorization": f"Bearer {access_token}"}
    existing_id = _find_file_id(access_token, name, folder_id)
    content_bytes = content.encode("utf-8")

    if existing_id:
        resp = requests.patch(
            f"https://www.googleapis.com/upload/drive/v3/files/{existing_id}",
            headers={**headers, "Content-Type": mime_type},
            params={"uploadType": "media"},
            data=content_bytes,
            timeout=30,
        )
        resp.raise_for_status()
        return existing_id

    metadata = {"name": name, "parents": [folder_id]}
    boundary = "garmin-ai-sync-boundary"
    multipart_body = (
        f"--{boundary}\r\n"
        "Content-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{json.dumps(metadata)}\r\n"
        f"--{boundary}\r\n"
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode("utf-8") + content_bytes + f"\r\n--{boundary}--".encode("utf-8")

    resp = requests.post(
        "https://www.googleapis.com/upload/drive/v3/files",
        headers={
            **headers,
            "Content-Type": f"multipart/related; boundary={boundary}",
        },
        params={"uploadType": "multipart"},
        data=multipart_body,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def write_json(access_token: str, folder_id: str, name: str, data) -> str:
    return write_file(
        access_token, folder_id, name, json.dumps(data, indent=2, ensure_ascii=False), "application/json"
    )


def fmt(value, unit: str = "", decimals: int | None = None) -> str:
    """Render a value for Markdown: NO_DATA sentinel when missing, never a bare 0."""
    if value is None:
        return NO_DATA
    if decimals is not None and isinstance(value, (int, float)):
        value = round(value, decimals)
    return f"{value}{unit}"
