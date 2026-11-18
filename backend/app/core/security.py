"""Password, token e confronti sicuri. Solo libreria standard (nessuna dipendenza compilata)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass

# scrypt: N=2^15, r=8, p=1 → 32 MiB per hash. Compromesso tra resistenza agli attacchi e memoria
# disponibile su hosting condiviso. I parametri sono salvati con l'hash: alzarli in futuro
# fa ricalcolare l'hash al login successivo (needs_rehash).
SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 1
_SCRYPT_MAXMEM = 64 * 1024 * 1024
_SALT_BYTES = 16
_KEY_BYTES = 32

PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 128


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(_SALT_BYTES)
    key = hashlib.scrypt(
        password.encode(),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        maxmem=_SCRYPT_MAXMEM,
        dklen=_KEY_BYTES,
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(key)}"


@dataclass(frozen=True)
class _Parsed:
    n: int
    r: int
    p: int
    salt: bytes
    key: bytes


def _parse(stored: str) -> _Parsed | None:
    parts = stored.split("$")
    if len(parts) != 6 or parts[0] != "scrypt":
        return None
    try:
        return _Parsed(
            int(parts[1]), int(parts[2]), int(parts[3]), _unb64(parts[4]), _unb64(parts[5])
        )
    except (ValueError, TypeError):
        return None


# Hash fittizio: si verifica comunque una password anche se l'utente non esiste, così il tempo
# di risposta non rivela quali email sono registrate.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def verify_password(password: str, stored: str | None) -> bool:
    parsed = _parse(stored or _DUMMY_HASH) or _parse(_DUMMY_HASH)
    if parsed is None:  # impossibile: _DUMMY_HASH è generato da hash_password
        raise RuntimeError("hash fittizio non valido")
    key = hashlib.scrypt(
        password.encode(),
        salt=parsed.salt,
        n=parsed.n,
        r=parsed.r,
        p=parsed.p,
        maxmem=_SCRYPT_MAXMEM,
        dklen=len(parsed.key),
    )
    return stored is not None and hmac.compare_digest(key, parsed.key)


def needs_rehash(stored: str) -> bool:
    parsed = _parse(stored)
    return parsed is None or (parsed.n, parsed.r, parsed.p) != (SCRYPT_N, SCRYPT_R, SCRYPT_P)


def password_problem(password: str, *, email: str = "", full_name: str = "") -> str | None:
    """Messaggio d'errore in italiano se la password non è accettabile, altrimenti None."""
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"La password deve avere almeno {PASSWORD_MIN_LENGTH} caratteri."
    if len(password) > PASSWORD_MAX_LENGTH:
        return f"La password può avere al massimo {PASSWORD_MAX_LENGTH} caratteri."
    lowered = password.lower()
    local_part = email.split("@", 1)[0].lower()
    if len(local_part) >= 4 and local_part in lowered:
        return "La password non può contenere il tuo indirizzo email."
    for word in full_name.lower().split():
        if len(word) >= 4 and word in lowered:
            return "La password non può contenere il tuo nome."
    if len(set(password)) < 5:
        return "La password è troppo semplice: usa caratteri più vari."
    return None


def new_token() -> str:
    """Token opaco non prevedibile (256 bit) da inviare all'utente o in un cookie."""
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    """Nel database si salva solo l'hash del token: una copia del DB non permette di usarli."""
    return hashlib.sha256(token.encode()).hexdigest()


def normalize_email(email: str) -> str:
    return email.strip().lower()
