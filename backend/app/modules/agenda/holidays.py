"""Festività nazionali italiane, calcolate (nessuna tabella da aggiornare ogni anno).

Le feste patronali sono locali: lo studio le inserisce come chiusura.
"""

from __future__ import annotations

from datetime import date, timedelta
from functools import cache


def easter_sunday(year: int) -> date:
    """Domenica di Pasqua (calendario gregoriano, algoritmo di Meeus/Jones/Butcher)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ll = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ll) // 451
    month, day = divmod(h + ll - 7 * m + 114, 31)
    return date(year, month, day + 1)


@cache
def italian_holidays(year: int) -> dict[date, str]:
    easter = easter_sunday(year)
    days = {
        date(year, 1, 1): "Capodanno",
        date(year, 1, 6): "Epifania",
        easter: "Pasqua",
        easter + timedelta(days=1): "Lunedì dell'Angelo",
        date(year, 4, 25): "Festa della Liberazione",
        date(year, 5, 1): "Festa del Lavoro",
        date(year, 6, 2): "Festa della Repubblica",
        date(year, 8, 15): "Ferragosto",
        date(year, 11, 1): "Ognissanti",
        date(year, 12, 8): "Immacolata Concezione",
        date(year, 12, 25): "Natale",
        date(year, 12, 26): "Santo Stefano",
    }
    if year >= 2026:  # San Francesco d'Assisi, di nuovo festa nazionale dal 2026 (L. 151/2025)
        days[date(year, 10, 4)] = "San Francesco d'Assisi"
    return days


def holiday_name(day: date) -> str | None:
    return italian_holidays(day.year).get(day)
