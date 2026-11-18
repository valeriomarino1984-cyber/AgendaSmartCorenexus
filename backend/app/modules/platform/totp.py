"""Codici a 6 cifre delle app di autenticazione (TOTP, RFC 6238), solo libreria standard.

Il segreto di ogni persona non è salvato: si ricava con HMAC dalla chiave del server e da un
sale casuale salvato nel database.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import struct
from urllib.parse import quote, urlencode

STEP_SECONDS = 30
DIGITS = 6
WINDOW = 1  # tolleranza: un intervallo prima e uno dopo (orologio del telefono non preciso)
ISSUER = "CoreNexus Agenda"


def derive_secret(server_key: bytes, salt: str) -> bytes:
    return hmac.new(server_key, b"totp:" + salt.encode(), hashlib.sha256).digest()[:20]


def b32(secret: bytes) -> str:
    return base64.b32encode(secret).decode().rstrip("=")


def code_at(secret: bytes, step: int, digits: int = DIGITS) -> str:
    mac = hmac.new(secret, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    value = struct.unpack(">I", mac[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10**digits).zfill(digits)


def verify(secret: bytes, code: str, now: float, last_step: int | None) -> int | None:
    """Intervallo del codice se valido e mai usato prima, altrimenti None."""
    code = code.strip().replace(" ", "")
    if len(code) != DIGITS or not code.isdigit():
        return None
    current = int(now // STEP_SECONDS)
    for step in range(current - WINDOW, current + WINDOW + 1):
        if last_step is not None and step <= last_step:
            continue
        if hmac.compare_digest(code_at(secret, step), code):
            return step
    return None


def otpauth_uri(secret: bytes, account: str) -> str:
    """Indirizzo da mostrare come QR per aggiungere l'account nell'app di autenticazione."""
    label = quote(f"{ISSUER}:{account}")
    params = urlencode(
        {"secret": b32(secret), "issuer": ISSUER, "digits": DIGITS, "period": STEP_SECONDS}
    )
    return f"otpauth://totp/{label}?{params}"
