"""Profili professionali: prestazioni consigliate per categoria di studio.

Sono un punto di partenza modificabile: lo studio può cambiarle, disattivarle o aggiungerne altre.
Le categorie senza profilo dedicato ricevono il profilo generico.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ServicePreset:
    name: str
    duration_minutes: int
    mode: str = "in_person"
    preparation_minutes: int = 0
    color: str = "#0071e3"


@dataclass(frozen=True)
class Profile:
    code: str
    label: str
    services: tuple[ServicePreset, ...]


_FISIO = Profile(
    "fisioterapista",
    "Fisioterapista",
    (
        ServicePreset("Valutazione fisioterapica", 60, preparation_minutes=10, color="#0071e3"),
        ServicePreset("Seduta di fisioterapia", 45, preparation_minutes=10, color="#30b0c7"),
        ServicePreset("Terapia manuale", 30, preparation_minutes=10, color="#5856d6"),
    ),
)
_OSTEO = Profile(
    "osteopata",
    "Osteopata",
    (
        ServicePreset("Prima visita osteopatica", 60, preparation_minutes=10, color="#0071e3"),
        ServicePreset("Trattamento osteopatico", 45, preparation_minutes=10, color="#30b0c7"),
    ),
)
_NUTRI = Profile(
    "nutrizionista",
    "Nutrizionista",
    (
        ServicePreset("Prima visita", 60, color="#0071e3"),
        ServicePreset("Controllo", 30, color="#30b0c7"),
        ServicePreset("Controllo online", 30, mode="online", color="#5856d6"),
    ),
)
_PSICO = Profile(
    "psicologo",
    "Psicologa / Psicologo",
    (
        ServicePreset("Primo colloquio", 60, color="#0071e3"),
        ServicePreset("Colloquio", 50, color="#30b0c7"),
        ServicePreset("Colloquio online", 50, mode="online", color="#5856d6"),
    ),
)
GENERIC = Profile(
    "generico",
    "Profilo generico",
    (
        ServicePreset("Primo incontro", 60, color="#0071e3"),
        ServicePreset("Appuntamento", 30, color="#30b0c7"),
    ),
)

_BY_BUSINESS_TYPE: dict[str, Profile] = {
    "fisioterapista": _FISIO,
    "osteopata": _OSTEO,
    "nutrizionista": _NUTRI,
    "biologo_nutrizionista": _NUTRI,
    "psicologo": _PSICO,
    "psicoterapeuta": _PSICO,
}


def profile_for(business_type: str | None) -> Profile:
    return _BY_BUSINESS_TYPE.get(business_type or "", GENERIC)
