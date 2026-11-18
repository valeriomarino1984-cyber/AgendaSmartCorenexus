"""Regole senza database: numeri di telefono e profili professionali."""

from __future__ import annotations

import pytest

from app.modules.catalog.phone import InvalidPhoneError, to_e164
from app.modules.catalog.presets import GENERIC, profile_for


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("333 123 4567", "+393331234567"),
        ("+39 333-123.4567", "+393331234567"),
        ("0039 333 1234567", "+393331234567"),
        ("+41 79 123 45 67", "+41791234567"),
        ("02 1234567", "+39021234567"),
        ("(06) 123456", "+3906123456"),
    ],
)
def test_phone_normalization(raw: str, expected: str) -> None:
    assert to_e164(raw) == expected


@pytest.mark.parametrize("raw", ["", "abc", "+12", "333 abc", "+0 333 1234567", "1" * 20, "++39 3"])
def test_phone_rejects_invalid(raw: str) -> None:
    with pytest.raises(InvalidPhoneError):
        to_e164(raw)


def test_profiles_match_approved_presets() -> None:
    def summary(code: str) -> list[tuple[str, int, str]]:
        return [(s.name, s.duration_minutes, s.mode) for s in profile_for(code).services]

    assert summary("fisioterapista") == [
        ("Valutazione fisioterapica", 60, "in_person"),
        ("Seduta di fisioterapia", 45, "in_person"),
        ("Terapia manuale", 30, "in_person"),
    ]
    assert summary("osteopata") == [
        ("Prima visita osteopatica", 60, "in_person"),
        ("Trattamento osteopatico", 45, "in_person"),
    ]
    nutri = [
        ("Prima visita", 60, "in_person"),
        ("Controllo", 30, "in_person"),
        ("Controllo online", 30, "online"),
    ]
    assert summary("nutrizionista") == summary("biologo_nutrizionista") == nutri
    psico = [
        ("Primo colloquio", 60, "in_person"),
        ("Colloquio", 50, "in_person"),
        ("Colloquio online", 50, "online"),
    ]
    assert summary("psicologo") == summary("psicoterapeuta") == psico


@pytest.mark.parametrize("code", ["estetista", "altro", "massoterapista", "", None])
def test_other_categories_get_generic_profile(code: str | None) -> None:
    assert profile_for(code) is GENERIC
