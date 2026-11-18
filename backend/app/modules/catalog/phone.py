"""Normalizzazione dei numeri di telefono in formato E.164, senza dipendenze esterne.

Regole: "+" iniziale mantenuto, "00" iniziale diventa "+", altrimenti si assume l'Italia (+39).
Si accettano 6-15 cifre totali (limite E.164). Spazi, punti, trattini e parentesi sono ignorati.
"""

from __future__ import annotations

import re

_ALLOWED = re.compile(r"^\+?[0-9 ()./-]+$")
DEFAULT_COUNTRY_CODE = "39"


class InvalidPhoneError(ValueError):
    pass


def to_e164(raw: str) -> str:
    value = raw.strip()
    if not value or not _ALLOWED.match(value):
        raise InvalidPhoneError("Numero di telefono non valido.")
    digits = re.sub(r"\D", "", value)
    if value.startswith("+"):
        number = digits
    elif digits.startswith("00"):
        number = digits[2:]
    else:
        number = DEFAULT_COUNTRY_CODE + digits
    if not 6 <= len(number) <= 15 or number.startswith("0"):
        raise InvalidPhoneError("Numero di telefono non valido.")
    return "+" + number
