"""One-time interactive Garmin login (email + password + 2FA).

Runs as a background process because this session cannot relay live
keyboard input into a running program. The prompt_mfa callback polls a
small file instead of reading stdin: Garmin has already sent the 2FA code
to the user by the time this callback is invoked (the login strategy
triggers delivery before calling prompt_mfa), and a separate short-lived
process (garmin_mfa_submit.py) writes the code the user reports into that
file once we have it.

The password is read only from an environment variable, used once to
call garminconnect's login(), and never written to disk. After a
successful login only the resulting session token is persisted, and only
in encrypted form (see crypto_utils.encrypt_to_file) - never the password,
never a plaintext token.
"""

from __future__ import annotations

import os
import time

from garminconnect import Garmin

from crypto_utils import SECRETS_DIR, encrypt_to_file

TOKEN_FILE = SECRETS_DIR / "garmin_token.enc"
STATUS_FILE = SECRETS_DIR / "garmin_login_status.txt"
MFA_CODE_FILE = SECRETS_DIR / "garmin_mfa_code.txt"

MFA_TIMEOUT_SECONDS = 300


def _set_status(text: str) -> None:
    STATUS_FILE.write_text(text)
    STATUS_FILE.chmod(0o600)


def _prompt_mfa() -> str:
    _set_status("waiting_for_mfa")
    deadline = time.time() + MFA_TIMEOUT_SECONDS
    while time.time() < deadline:
        if MFA_CODE_FILE.exists():
            code = MFA_CODE_FILE.read_text().strip()
            MFA_CODE_FILE.unlink()
            _set_status("verifying")
            return code
        time.sleep(2)
    raise TimeoutError("Kein 2FA-Code innerhalb von 5 Minuten erhalten")


def main() -> None:
    email = os.environ["GARMIN_EMAIL"]
    password = os.environ["GARMIN_PASSWORD"]

    SECRETS_DIR.mkdir(mode=0o700, exist_ok=True)
    MFA_CODE_FILE.unlink(missing_ok=True)
    _set_status("logging_in")

    try:
        garmin = Garmin(email=email, password=password, prompt_mfa=_prompt_mfa)
        # Only mobile+requests reaches Garmin at all through this session's
        # TLS-terminating proxy - the cffi strategies get connection resets
        # (their spoofed TLS fingerprint doesn't survive re-termination) and
        # portal+requests hits Cloudflare's bot challenge. Skipping the other
        # three avoids tripping Cloudflare three more times per attempt.
        garmin.client.skip_strategies = {
            "mobile+cffi",
            "widget+cffi",
            "portal+cffi",
            "portal+requests",
        }
        garmin.login()
    except Exception as e:  # noqa: BLE001 - report any failure back via status file
        _set_status(f"failed: {e}")
        return

    encrypt_to_file(TOKEN_FILE, garmin.client.dumps())
    _set_status("success")


if __name__ == "__main__":
    main()
