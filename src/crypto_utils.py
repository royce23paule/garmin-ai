"""Encryption helper for tokens at rest.

Tokens (Google refresh token, Garmin session token) are encrypted with a
locally generated Fernet key before being written to disk. The key lives
next to the encrypted files in secrets/, outside git. This protects
against accidental disclosure (logs, backups, a stray `cat`) - it does not
protect against an attacker with full read access to this session's
filesystem, since the key is stored there too.
"""

from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet

SECRETS_DIR = Path(__file__).resolve().parent.parent / "secrets"
KEY_FILE = SECRETS_DIR / "encryption.key"


def _load_or_create_key() -> bytes:
    SECRETS_DIR.mkdir(mode=0o700, exist_ok=True)
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()
    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)
    os.chmod(KEY_FILE, 0o600)
    return key


def encrypt_to_file(path: Path, plaintext: str) -> None:
    fernet = Fernet(_load_or_create_key())
    path.write_bytes(fernet.encrypt(plaintext.encode("utf-8")))
    os.chmod(path, 0o600)


def decrypt_from_file(path: Path) -> str:
    fernet = Fernet(_load_or_create_key())
    return fernet.decrypt(path.read_bytes()).decode("utf-8")
