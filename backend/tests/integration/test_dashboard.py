"""Numeri della dashboard: conteggi per stato, valore, occupazione, clienti nuovi, ruoli."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.integration.conftest import new_client
from tests.integration.test_accounts import sql
from tests.integration.test_agenda import Studio, at
from tests.integration.test_catalog import invite_and_join
from tests.integration.test_public_booking import book, booking, open_studio

API = "/api/v1"


def stats(c: TestClient, first: date, last: date | None = None, **extra: object) -> dict[str, Any]:
    r = c.get(
        f"{API}/dashboard/stats",
        params={"from": first.isoformat(), "to": (last or first).isoformat(), **extra},
    )
    assert r.status_code == 200, r.text
    out: dict[str, Any] = r.json()
    return out


def set_status(engine: Engine, appt_id: str, status: str) -> None:
    sql(engine, "UPDATE appointments SET status = :s WHERE id = :i", s=status, i=appt_id)


def test_counts_value_and_occupancy(app: FastAPI, owner_engine: Engine) -> None:
    st = Studio(app)
    st.c.patch(f"{API}/services/{st.services['Controllo']['id']}", json={"price": "50.00"})
    st.c.patch(f"{API}/services/{st.services['Prima visita']['id']}", json={"price": "80.00"})
    ids = [st.book(at(st.monday, h)).json()["id"] for h in (9, 10, 11)]
    visit = st.book(at(st.monday, 12), service="Prima visita").json()["id"]
    r = st.c.post(
        f"{API}/appointments/{ids[0]}/status", json={"version": 1, "status": "cancelled_by_staff"}
    )
    assert r.status_code == 200, r.text
    # Svolto e assente si possono segnare solo dopo l'orario: qui li impostiamo direttamente.
    set_status(owner_engine, ids[1], "completed")
    set_status(owner_engine, ids[2], "no_show")

    out = stats(st.c, st.monday)
    s = out["summary"]
    assert out["scope"] == "studio" and out["timezone"] == "Europe/Rome"
    assert (s["appointments"], s["completed"], s["no_show"], s["cancelled"], s["upcoming"]) == (
        4,
        1,
        1,
        1,
        1,
    )
    assert s["cancelled_by_staff"] == 1 and s["cancelled_by_client"] == 0
    assert s["cancellation_rate"] == 0.25 and s["no_show_rate"] == 0.5
    assert s["value_done"] == "50.00" and s["value_expected"] == "80.00"
    # Occupano l'agenda svolto (30), assente (30) e prima visita (60): 120 su 240 minuti.
    assert s["booked_minutes"] == 120 and s["available_minutes"] == 240
    assert s["occupancy"] == 0.5
    assert s["clients_seen"] == 1 and s["new_clients"] == 1
    assert out["trend"] == {
        "granularity": "day",
        "points": [
            {
                "key": st.monday.isoformat(),
                "appointments": 4,
                "completed": 1,
                "cancelled": 1,
                "no_show": 1,
            }
        ],
    }
    assert [(x["name"], x["appointments"]) for x in out["services"]] == [
        ("Controllo", 3),
        ("Prima visita", 1),
    ]
    assert out["professionals"][0]["name"] == "Anna Bianchi"
    assert out["professionals"][0]["occupancy"] == 0.5
    assert visit

    # Lo stesso cliente la settimana dopo non è più "nuovo".
    nxt = st.monday + timedelta(days=7)
    st.book(at(nxt, 9))
    later = stats(st.c, nxt)["summary"]
    assert later["clients_seen"] == 1 and later["new_clients"] == 0

    # Un cliente con un solo appuntamento disdetto non è "visto" né "nuovo"; lo diventa
    # quando prenota davvero, anche se la disdetta era prima.
    paolo = st.c.post(f"{API}/clients", json={"first_name": "Paolo", "last_name": "Neri"}).json()
    gone = st.book(at(st.monday, 9), client_id=paolo["id"]).json()
    st.c.post(
        f"{API}/appointments/{gone['id']}/status",
        json={"version": 1, "status": "cancelled_by_client"},
    )
    again = stats(st.c, st.monday)["summary"]
    assert again["clients_seen"] == 1 and again["new_clients"] == 1
    st.book(at(nxt, 10), client_id=paolo["id"])
    later = stats(st.c, nxt)["summary"]
    assert later["clients_seen"] == 2 and later["new_clients"] == 1


def test_empty_period_and_trend_shape(app: FastAPI) -> None:
    st = Studio(app)
    out = stats(st.c, st.monday, st.monday + timedelta(days=6))
    s = out["summary"]
    assert s["appointments"] == 0 and s["cancellation_rate"] is None and s["no_show_rate"] is None
    assert s["booked_minutes"] == 0 and s["occupancy"] == 0
    assert len(out["trend"]["points"]) == 7
    months = stats(st.c, date(2027, 1, 1), date(2027, 3, 31))["trend"]
    assert months["granularity"] == "month"
    assert [p["key"] for p in months["points"]] == ["2027-01", "2027-02", "2027-03"]


def test_period_validation_and_default(app: FastAPI) -> None:
    st = Studio(app)
    bad = [
        {"from": "2027-02-01", "to": "2027-01-01"},
        {"from": "2027-01-01", "to": "2028-02-01"},
    ]
    for params in bad:
        r = st.c.get(f"{API}/dashboard/stats", params=params)
        assert r.status_code == 422 and r.json()["error"]["code"] == "periodo_non_valido"
    r = st.c.get(f"{API}/dashboard/stats")
    assert r.status_code == 200
    first, last = date.fromisoformat(r.json()["from"]), date.fromisoformat(r.json()["to"])
    assert first.day == 1 and (last + timedelta(days=1)).day == 1 and first.month == last.month
    assert new_client(app).get(f"{API}/dashboard/stats").status_code == 401


def test_roles_and_professional_filter(app: FastAPI) -> None:
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
    pro.put(
        f"{API}/professionals/{luca}/availability",
        json={"rules": [{"weekday": 1, "start_time": "14:00", "end_time": "18:00"}]},
    )
    st.book(at(st.monday, 9))
    st.book(at(st.monday, 10))
    assert st.book(at(st.monday, 15), professional_id=luca).status_code == 201

    assert stats(st.c, st.monday)["summary"]["appointments"] == 3
    assert stats(sec, st.monday)["summary"]["appointments"] == 3
    only_luca = stats(st.c, st.monday, professional_id=luca)
    assert only_luca["summary"]["appointments"] == 1
    assert only_luca["summary"]["available_minutes"] == 240
    assert [p["name"] for p in only_luca["professionals"]] == ["Luca Moretti"]

    # Il professionista vede solo i propri numeri, anche senza filtro.
    own = stats(pro, st.monday)
    assert own["scope"] == "own" and own["summary"]["appointments"] == 1
    assert own["professional_id"] == luca
    r = pro.get(
        f"{API}/dashboard/stats",
        params={"from": str(st.monday), "to": str(st.monday), "professional_id": st.prof},
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "professionista_non_valido"


def test_studios_are_isolated_and_online_counted(app: FastAPI) -> None:
    a, slug = open_studio(app, "Studio Numeri A")
    b = Studio(app, "Studio Numeri B")
    assert book(new_client(app), slug, booking(a, start=at(a.monday, 9))).status_code == 201
    a.book(at(a.monday, 10))
    s = stats(a.c, a.monday)["summary"]
    assert s["appointments"] == 2 and s["online"] == 1 and s["online_rate"] == 0.5
    assert stats(b.c, b.monday)["summary"]["appointments"] == 0
    r = b.c.get(
        f"{API}/dashboard/stats",
        params={"from": str(a.monday), "to": str(a.monday), "professional_id": a.prof},
    )
    assert r.status_code == 422
