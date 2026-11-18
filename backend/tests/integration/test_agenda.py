"""Sprint 3: orari, orari liberi, appuntamenti, doppie prenotazioni, ruoli e isolamento."""

from __future__ import annotations

import threading
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.agenda.holidays import holiday_name
from tests.integration.conftest import new_client
from tests.integration.test_catalog import invite_and_join, new_studio

API = "/api/v1"
ROME = ZoneInfo("Europe/Rome")


def next_working_monday(weeks_ahead: int = 1) -> date:
    day = date.today() + timedelta(days=7 * weeks_ahead)
    day += timedelta(days=(7 - day.weekday()) % 7)
    while holiday_name(day) or any(holiday_name(day + timedelta(days=i)) for i in range(5)):
        day += timedelta(days=7)
    return day


def at(day: date, hh: int, mm: int = 0) -> str:
    return datetime.combine(day, time(hh, mm), tzinfo=ROME).isoformat()


class Studio:
    """Studio di nutrizione con orario lun-ven 9-13 per la titolare."""

    def __init__(self, app: FastAPI, name: str = "Studio Agenda") -> None:
        self.c = new_studio(app, name, "nutrizionista")
        self.prof = self.c.get(f"{API}/professionals").json()[0]["id"]
        self.services = {s["name"]: s for s in self.c.get(f"{API}/services").json()}
        self.client_id = self.c.post(
            f"{API}/clients", json={"first_name": "Giulia", "last_name": "Ferri"}
        ).json()["id"]
        r = self.c.put(
            f"{API}/professionals/{self.prof}/availability",
            json={
                "rules": [
                    {"weekday": d, "start_time": "09:00", "end_time": "13:00"} for d in range(1, 6)
                ]
            },
        )
        assert r.status_code == 200, r.text
        self.monday = next_working_monday()

    def book(
        self,
        start: str,
        service: str = "Controllo",
        client: TestClient | None = None,
        **extra: object,
    ) -> httpx.Response:
        body = {
            "client_id": self.client_id,
            "professional_id": self.prof,
            "service_id": self.services[service]["id"],
            "start_at": start,
            **extra,
        }
        r: httpx.Response = (client or self.c).post(f"{API}/appointments", json=body)
        return r

    def slots(self, service: str = "Controllo", day: date | None = None) -> list[str]:
        d = (day or self.monday).isoformat()
        r = self.c.get(
            f"{API}/slots",
            params={
                "professional_id": self.prof,
                "service_id": self.services[service]["id"],
                "from": d,
                "to": d,
            },
        )
        assert r.status_code == 200, r.text
        return [s["local"][11:] for s in r.json()["slots"]]


# ---------------------------------------------------------------- orari e orari liberi


def test_weekly_hours_and_slots(app: FastAPI) -> None:
    st = Studio(app)
    rules = st.c.get(f"{API}/professionals/{st.prof}/availability").json()
    assert [(r["weekday"], r["start_time"], r["end_time"]) for r in rules][:2] == [
        (1, "09:00", "13:00"),
        (2, "09:00", "13:00"),
    ]
    slots = st.slots("Prima visita")  # 60 minuti, passo 15
    assert slots[0] == "09:00" and slots[-1] == "12:00" and len(slots) == 13

    sunday = st.monday - timedelta(days=1)
    assert st.slots(day=sunday) == []

    r = st.c.put(
        f"{API}/professionals/{st.prof}/availability",
        json={
            "rules": [
                {"weekday": 1, "start_time": "09:00", "end_time": "12:00"},
                {"weekday": 1, "start_time": "11:00", "end_time": "13:00"},
            ]
        },
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "fasce_sovrapposte"


def test_exceptions_block_and_open(app: FastAPI) -> None:
    st = Studio(app)
    vac = st.c.post(
        f"{API}/availability-exceptions",
        json={
            "kind": "vacation",
            "professional_id": st.prof,
            "start_at": at(st.monday, 0),
            "end_at": at(st.monday + timedelta(days=1), 0),
        },
    )
    assert vac.status_code == 201, vac.text
    assert st.slots() == []
    assert st.c.delete(f"{API}/availability-exceptions/{vac.json()['id']}").status_code == 204
    assert st.slots() != []

    # Chiusura dello studio la mattina: vale per tutti i professionisti.
    st.c.post(
        f"{API}/availability-exceptions",
        json={
            "kind": "closure",
            "start_at": at(st.monday, 9),
            "end_at": at(st.monday, 11),
            "reason": "Disinfestazione",
        },
    )
    assert st.slots()[0] == "11:00"

    # Apertura straordinaria di sabato.
    saturday = st.monday + timedelta(days=5)
    st.c.post(
        f"{API}/availability-exceptions",
        json={
            "kind": "extra",
            "professional_id": st.prof,
            "start_at": at(saturday, 10),
            "end_at": at(saturday, 11),
        },
    )
    assert st.slots(day=saturday) == ["10:00", "10:15", "10:30"]

    listed = st.c.get(
        f"{API}/availability-exceptions",
        params={"from": at(st.monday, 0), "to": at(st.monday + timedelta(days=7), 0)},
    ).json()
    assert sorted(e["kind"] for e in listed) == ["closure", "extra"]


# ---------------------------------------------------------------- appuntamenti


def test_create_appointment_and_online_link(app: FastAPI) -> None:
    st = Studio(app)
    r = st.book(at(st.monday, 9), "Controllo online")
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["status"] == "confirmed" and a["is_online"] is True
    assert a["video_url"].startswith("https://meet.jit.si/CN-") and len(a["video_url"]) > 40
    assert "Giulia" not in a["video_url"] and "Ferri" not in a["video_url"]
    assert len(a["public_code"]) == 8 and a["duration_minutes"] == 30
    assert a["start_at"].endswith("Z")

    other = st.book(at(st.monday, 10), "Controllo online").json()
    assert other["video_url"] != a["video_url"]  # una stanza diversa per ogni appuntamento

    in_studio = st.book(at(st.monday, 11), "Controllo").json()
    assert in_studio["is_online"] is False and in_studio["video_url"] is None
    r = st.book(at(st.monday, 12), "Controllo", is_online=True)
    assert r.status_code == 422 and r.json()["error"]["code"] == "modalita_non_valida"

    assert "09:00" not in st.slots() and "09:30" in st.slots()

    detail = st.c.get(f"{API}/appointments/{a['id']}").json()
    assert detail["events"][0]["type"] == "created"
    listed = st.c.get(
        f"{API}/appointments",
        params={"from": at(st.monday, 0), "to": at(st.monday + timedelta(days=1), 0)},
    ).json()
    assert [x["client_name"] for x in listed] == ["Giulia Ferri"] * 3
    assert listed[0]["service_name"] == "Controllo online" and listed[0]["color"].startswith("#")


def test_no_overlap_including_preparation(app: FastAPI) -> None:
    st = Studio(app)
    st.c.patch(f"{API}/services/{st.services['Controllo']['id']}", json={"preparation_minutes": 15})
    assert st.book(at(st.monday, 9)).status_code == 201  # 9:00-9:30 + 15' → libero dalle 9:45
    for start in (
        at(st.monday, 9),
        at(st.monday, 9, 15),
        at(st.monday, 9, 30),
        at(st.monday, 8, 45),
    ):
        r = st.book(start, force=True)
        assert r.status_code == 409 and r.json()["error"]["code"] == "orario_occupato", start
    assert st.book(at(st.monday, 9, 45)).status_code == 201


def test_cancelled_appointment_frees_the_slot(app: FastAPI) -> None:
    st = Studio(app)
    a = st.book(at(st.monday, 9)).json()
    r = st.c.post(
        f"{API}/appointments/{a['id']}/status",
        json={"version": a["version"], "status": "cancelled_by_client", "reason": "Influenza"},
    )
    assert r.status_code == 200 and r.json()["status"] == "cancelled_by_client"
    assert st.book(at(st.monday, 9)).status_code == 201
    r = st.c.patch(f"{API}/appointments/{a['id']}", json={"version": 2, "notes": "x"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "appuntamento_chiuso"


def test_outside_hours_needs_confirmation(app: FastAPI) -> None:
    st = Studio(app)
    r = st.book(at(st.monday, 14))
    assert r.status_code == 409 and r.json()["error"]["code"] == "fuori_orario"
    assert st.book(at(st.monday, 14), force=True).status_code == 201

    year = st.monday.year + 1
    christmas = date(year, 12, 25)
    r = st.book(datetime.combine(christmas, time(10), tzinfo=ROME).isoformat())
    assert r.status_code == 409 and "Natale" in r.json()["error"]["message"]


def test_concurrent_bookings_only_one_wins(app: FastAPI) -> None:
    """Richieste contemporanee sullo stesso orario: una sola riesce, le altre ricevono 409."""
    st = Studio(app)
    n = 8
    barrier = threading.Barrier(n)
    results: list[int] = []
    lock = threading.Lock()
    cookies = dict(st.c.cookies)

    def attempt() -> None:
        c = new_client(app)
        c.cookies.update(cookies)
        barrier.wait()
        r = st.book(at(st.monday, 10), client=c)
        with lock:
            results.append(r.status_code)

    threads = [threading.Thread(target=attempt) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == [201] + [409] * (n - 1), results
    listed = st.c.get(
        f"{API}/appointments",
        params={"from": at(st.monday, 0), "to": at(st.monday + timedelta(days=1), 0)},
    ).json()
    assert len(listed) == 1


def test_concurrent_moves_into_same_slot(app: FastAPI) -> None:
    st = Studio(app)
    first = st.book(at(st.monday, 9)).json()
    second = st.book(at(st.monday, 11)).json()
    target = at(st.monday, 12)
    barrier = threading.Barrier(2)
    codes: list[int] = []
    cookies = dict(st.c.cookies)

    def move(a: dict[str, object]) -> None:
        c = new_client(app)
        c.cookies.update(cookies)
        barrier.wait()
        r = c.patch(
            f"{API}/appointments/{a['id']}", json={"version": a["version"], "start_at": target}
        )
        codes.append(r.status_code)

    threads = [threading.Thread(target=move, args=(a,)) for a in (first, second)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(codes) == [200, 409]


def test_move_with_version_check(app: FastAPI) -> None:
    st = Studio(app)
    a = st.book(at(st.monday, 9)).json()
    r = st.c.patch(
        f"{API}/appointments/{a['id']}", json={"version": 1, "start_at": at(st.monday, 11)}
    )
    assert r.status_code == 200 and r.json()["version"] == 2
    assert (
        r.json()["start_at"] == datetime.combine(st.monday, time(10)).isoformat() + "Z"
    )  # 11:00 CET

    stale = st.c.patch(
        f"{API}/appointments/{a['id']}", json={"version": 1, "start_at": at(st.monday, 12)}
    )
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "modificato_da_altri"

    # Cambio di prestazione: la durata segue la nuova prestazione.
    r = st.c.patch(
        f"{API}/appointments/{a['id']}",
        json={"version": 2, "service_id": st.services["Prima visita"]["id"]},
    )
    assert r.status_code == 200 and r.json()["duration_minutes"] == 60

    events = st.c.get(f"{API}/appointments/{a['id']}").json()["events"]
    assert [e["type"] for e in events] == ["created", "rescheduled", "rescheduled"]


def test_status_rules(app: FastAPI) -> None:
    st = Studio(app)
    a = st.book(at(st.monday, 9), status="pending").json()
    assert a["status"] == "pending"
    r = st.c.post(
        f"{API}/appointments/{a['id']}/status", json={"version": 1, "status": "confirmed"}
    )
    assert r.status_code == 200 and r.json()["version"] == 2
    r = st.c.post(
        f"{API}/appointments/{a['id']}/status", json={"version": 2, "status": "completed"}
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "appuntamento_futuro"
    r = st.c.post(
        f"{API}/appointments/{a['id']}/status", json={"version": 2, "status": "cancelled_by_staff"}
    )
    assert r.status_code == 200
    r = st.c.post(
        f"{API}/appointments/{a['id']}/status", json={"version": 3, "status": "confirmed"}
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "cambio_stato_non_valido"


def test_validation(app: FastAPI) -> None:
    st = Studio(app)
    other_prof = st.c.post(f"{API}/professionals", json={"name": "Elena Rossi"}).json()["id"]
    # Prestazione abilitata solo alla titolare.
    st.c.patch(
        f"{API}/services/{st.services['Controllo']['id']}", json={"professional_ids": [st.prof]}
    )
    r = st.book(at(st.monday, 9), professional_id=other_prof, force=True)
    assert r.status_code == 422 and r.json()["error"]["code"] == "prestazione_non_abilitata"
    r = st.book("2026-11-23T09:00:00")  # senza fuso
    assert r.status_code == 422
    st.c.delete(f"{API}/clients/{st.client_id}")
    r = st.book(at(st.monday, 9))
    assert r.status_code == 422 and r.json()["error"]["code"] == "cliente_non_valido"


# ---------------------------------------------------------------- ruoli e isolamento


def test_roles(app: FastAPI) -> None:
    st = Studio(app)
    pro = invite_and_join(st.c, "professional", "Luca Moretti")
    sec = invite_and_join(st.c, "secretary", "Sara Galli")
    luca = next(
        p["id"] for p in st.c.get(f"{API}/professionals").json() if p["name"] == "Luca Moretti"
    )
    st.c.patch(
        f"{API}/services/{st.services['Controllo']['id']}",
        json={"professional_ids": [st.prof, luca]},
    )
    owner_appt = st.book(at(st.monday, 9)).json()

    # Il professionista gestisce i propri orari e appuntamenti, non quelli degli altri.
    r = pro.put(
        f"{API}/professionals/{luca}/availability",
        json={"rules": [{"weekday": 1, "start_time": "14:00", "end_time": "18:00"}]},
    )
    assert r.status_code == 200
    r = pro.put(f"{API}/professionals/{st.prof}/availability", json={"rules": []})
    assert r.status_code == 403 and r.json()["error"]["code"] == "agenda_di_altri"
    assert st.book(at(st.monday, 9, 30), client=pro).status_code == 403
    assert st.book(at(st.monday, 15), client=pro, professional_id=luca).status_code == 201
    day = {"from": at(st.monday, 0), "to": at(st.monday + timedelta(days=1), 0)}
    assert [a["professional_name"] for a in pro.get(f"{API}/appointments", params=day).json()] == [
        "Luca Moretti"
    ]
    assert pro.get(f"{API}/appointments/{owner_appt['id']}").status_code == 404

    # La segreteria gestisce l'agenda di tutti, ma non chiude lo studio.
    assert st.book(at(st.monday, 10), client=sec).status_code == 201
    assert len(sec.get(f"{API}/appointments", params=day).json()) == 3
    r = sec.post(
        f"{API}/availability-exceptions",
        json={"kind": "closure", "start_at": at(st.monday, 0), "end_at": at(st.monday, 23)},
    )
    assert r.status_code == 403

    guest = new_client(app)
    assert guest.get(f"{API}/appointments", params=day).status_code == 401


def test_agenda_isolation_between_studios(app: FastAPI) -> None:
    a, b = Studio(app, "Studio A"), Studio(app, "Studio B")
    appt = a.book(at(a.monday, 9)).json()
    day = {"from": at(a.monday, 0), "to": at(a.monday + timedelta(days=1), 0)}
    assert b.c.get(f"{API}/appointments", params=day).json() == []
    assert b.c.get(f"{API}/appointments/{appt['id']}").status_code == 404
    r = b.c.patch(f"{API}/appointments/{appt['id']}", json={"version": 1, "notes": "rubato"})
    assert r.status_code == 404
    r = b.c.post(
        f"{API}/appointments/{appt['id']}/status",
        json={"version": 1, "status": "cancelled_by_staff"},
    )
    assert r.status_code == 404
    # B non può prenotare un cliente, un professionista o una prestazione di A.
    assert b.book(at(b.monday, 10), client_id=a.client_id).status_code == 422
    assert b.book(at(b.monday, 10), professional_id=a.prof).status_code == 404
    r = b.c.get(
        f"{API}/slots",
        params={
            "professional_id": a.prof,
            "service_id": b.services["Controllo"]["id"],
            "from": b.monday.isoformat(),
            "to": b.monday.isoformat(),
        },
    )
    assert r.status_code == 404
    assert b.c.get(f"{API}/professionals/{a.prof}/availability").status_code == 404
    assert a.c.get(f"{API}/appointments/{appt['id']}").json()["status"] == "confirmed"


def test_overlap_check_sees_bookings_committed_after_snapshot(app: FastAPI) -> None:
    """In REPEATABLE READ una lettura normale vedrebbe la "foto" presa a inizio transazione:
    il controllo delle sovrapposizioni deve invece vedere anche ciò che è stato confermato dopo.
    """
    import uuid

    import pytest
    from sqlalchemy import select

    from app.core.errors import ConflictError
    from app.models.agenda import Appointment
    from app.models.catalog import Location
    from app.modules.agenda import service as agenda

    st = Studio(app)
    tenant_id = uuid.UUID(st.c.get(f"{API}/auth/me").json()["tenant"]["id"])
    prof_id = uuid.UUID(st.prof)
    start = datetime.combine(st.monday, time(10), tzinfo=ROME)
    start_utc = agenda.to_utc(start)
    db = app.state.db
    with db.tenant_session(tenant_id) as s:
        s.scalars(select(Appointment)).all()  # la "foto" della transazione parte qui
        loc = s.scalars(select(Location)).first()
        assert loc is not None
        assert st.book(start.isoformat()).status_code == 201  # un'altra transazione conferma
        with pytest.raises(ConflictError):
            agenda._check_slot(
                s,
                professional_id=prof_id,
                loc=loc,
                start=start_utc,
                end=start_utc + timedelta(minutes=30),
                buffer_end=start_utc + timedelta(minutes=30),
                exclude=None,
                force=True,
            )
