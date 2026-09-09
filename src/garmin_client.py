"""Resume a Garmin session from the encrypted token saved by the one-time
login (garmin_login_flow.py). Used by every automated sync run - no
password or 2FA needed as long as the stored token is still valid.
"""

from __future__ import annotations

from garminconnect import Garmin

from crypto_utils import SECRETS_DIR, decrypt_from_file, encrypt_to_file

TOKEN_FILE = SECRETS_DIR / "garmin_token.enc"


class GarminNotLoggedIn(Exception):
    """Raised when no valid stored token exists; run garmin_login_flow.py first."""


def get_client() -> Garmin:
    if not TOKEN_FILE.exists():
        raise GarminNotLoggedIn(
            "Kein gespeichertes Garmin-Token gefunden. "
            "Erst den einmaligen Login (garmin_login_flow.py) ausfuehren."
        )

    tokenstore = decrypt_from_file(TOKEN_FILE)
    garmin = Garmin()
    try:
        garmin.login(tokenstore=tokenstore)
    except Exception as e:
        raise GarminNotLoggedIn(
            f"Gespeichertes Garmin-Token wurde abgelehnt (evtl. abgelaufen): {e}"
        ) from e

    # Re-persist: login() may have silently refreshed the token, and we want
    # the freshest one on disk so the session keeps extending itself.
    encrypt_to_file(TOKEN_FILE, garmin.client.dumps())
    return garmin
