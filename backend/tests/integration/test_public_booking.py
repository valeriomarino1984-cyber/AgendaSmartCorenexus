"""Prenotazione online: pagina pubblica, orari liberi, prenotazione, doppioni, limiti."""

from __future__ import annotations

import secrets
from datetime import timedelta

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.modules.email.sender import MEMORY_OUTBOX
from tests.integration.conftest import new_client
from tests.integration.test_accounts import sql, unique_email
from tests.integration.test_agenda import Studio, at

API = "/api/v1"


def open_studio(
    app: FastAPI, name: str = "Studio Online", **settings: object
) -> tuple[Studio, str]:
    st = Studio(app, name)
    r = st.c.put(
        f"{API}/tenants/current",
        json={"online_booking_enabled": True, "online_booking_min_notice_hours": 0, **settings},
    )
    assert r.status_code == 200, r.text
    slug = st.c.get(f"{API}/tenants/current").json()["slug"]
    return st, slug


def booking(
    st: Studio, *, start: str, email: str | None = None, service: str = "Controllo", **extra: object
) -> dict[str, object]:
    return {
        "service_id": st.services[service]["id"],
        "start_at": start,
        "first_name": "Marta",
        "last_name": "Gallo",
        "email": email or unique_email("pubblico"),
        "phone": "333 999 8888",
        "privacy_accepted": True,
        "booking_key": secrets.token_urlsafe(16),
        **extra,
    }


def book(c: TestClient, slug: str, body: dict[str, object]) -> httpx.Response:
    r: httpx.Response = c.post(f"{API}/public/studios/{slug}/bookings", json=body)
    return r


def test_page_exists_only_when_enabled(app: FastAPI) -> None:
    st = Studio(app, "Studio Chiuso")
    slug = st.c.get(f"{API}/tenants/current").json()["slug"]
    guest = new_client(app)
    assert guest.get(f"{API}/public/studios/{slug}").status_code == 404
    st.c.put(f"{API}/tenants/current", json={"online_booking_enabled": True})
    info = guest.get(f"{API}/public/studios/{slug}").json()
    assert info["name"] == "Studio Chiuso" and len(info["services"]) == 3
    assert info["professionals"][0]["name"] == "Anna Bianchi"
    assert guest.get(f"{API}/public/studios/inesistente").status_code == 404


def test_hidden_services_and_professionals(app: FastAPI) -> None:
    st, slug = open_studio(app)
    st.c.patch(
        f"{API}/services/{st.services['Prima visita']['id']}", json={"public_visible": False}
    )
    st.c.patch(f"{API}/professionals/{st.prof}", json={"public_booking": False})
    info = new_client(app).get(f"{API}/public/studios/{slug}").json()
    assert info["services"] == [] and info["professionals"] == []
    st.c.patch(f"{API}/professionals/{st.prof}", json={"public_booking": True})
    names = [
        s["name"] for s in new_client(app).get(f"{API}/public/studios/{slug}").json()["services"]
    ]
    assert "Prima visita" not in names and "Controllo" in names


def test_slots_respect_hours_notice_and_days_ahead(app: FastAPI) -> None:
    st, slug = open_studio(app, online_booking_days_ahead=30)
    guest = new_client(app)
    d = st.monday.isoformat()
    r = guest.get(
        f"{API}/public/studios/{slug}/slots",
        params={"service_id": st.services["Controllo"]["id"], "from": d, "to": d},
    )
    day = r.json()["days"][d]
    assert (
        day[0]["time"] == "09:00"
        and day[-1]["time"] == "12:30"
        and day[0]["professional_ids"] == [st.prof]
    )
    far = (st.monday + timedelta(days=60)).isoformat()
    r = guest.get(
        f"{API}/public/studios/{slug}/slots",
        params={"service_id": st.services["Controllo"]["id"], "from": far, "to": far},
    )
    assert r.json()["days"] == {}


def test_booking_creates_client_appointment_and_confirmation(app: FastAPI) -> None:
    st, slug = open_studio(app)
    email = unique_email("marta")
    r = book(new_client(app), slug, booking(st, start=at(st.monday, 10), email=email))
    assert r.status_code == 201, r.text
    out = r.json()
    assert (
        out["status"] == "confirmed"
        and out["service"] == "Controllo"
        and out["professional"] == "Anna Bianchi"
    )
    clients = st.c.get(f"{API}/clients", params={"q": "Gallo"}).json()["items"]
    assert (
        len(clients) == 1
        and clients[0]["email"] == email
        and clients[0]["phone"] == "+393339998888"
    )
    assert clients[0]["email_consent"] is False
    # La conferma parte anche senza consenso ai promemoria: l'ha chiesta il cliente prenotando.
    assert any(m.to == email and "Appuntamento confermato" in m.subject for m in MEMORY_OUTBOX)
    day = {"from": at(st.monday, 0), "to": at(st.monday + timedelta(days=1), 0)}
    appts = st.c.get(f"{API}/appointments", params=day).json()
    assert len(appts) == 1 and appts[0]["source"] == "public_booking"
    detail = st.c.get(f"{API}/appointments/{appts[0]['id']}").json()
    assert detail["events"][0]["actor_type"] == "client"
    reminder = next(n for n in detail["notifications"] if n["kind"] == "reminder")
    assert reminder["status"] == "pending"  # partirà solo con il consenso (verificato all'invio)


def test_returning_client_is_recognised_and_consents_recorded(app: FastAPI) -> None:
    st, slug = open_studio(app)
    email = unique_email("ritorno")
    assert (
        book(new_client(app), slug, booking(st, start=at(st.monday, 9), email=email)).status_code
        == 201
    )
    r = book(
        new_client(app),
        slug,
        booking(
            st,
            start=at(st.monday, 11),
            email=email.upper(),
            email_consent=True,
            marketing_consent=True,
        ),
    )
    assert r.status_code == 201
    clients = st.c.get(f"{API}/clients", params={"q": "Gallo"}).json()["items"]
    assert len(clients) == 1
    detail = st.c.get(f"{API}/clients/{clients[0]['id']}").json()
    assert detail["email_consent"] is True and detail["marketing_consent"] is True
    assert {(e["channel"], e["source"]) for e in detail["consent_history"]} == {
        ("email", "public_booking"),
        ("marketing", "public_booking"),
    }


def test_only_proposed_times_can_be_booked(app: FastAPI) -> None:
    st, slug = open_studio(app)
    guest = new_client(app)
    for start in (at(st.monday, 14), at(st.monday, 9, 5), at(st.monday - timedelta(days=1), 10)):
        r = book(guest, slug, booking(st, start=start))
        assert r.status_code == 409 and r.json()["error"]["code"] == "orario_non_disponibile", start


def test_same_slot_twice_and_double_submit(app: FastAPI) -> None:
    st, slug = open_studio(app)
    body = booking(st, start=at(st.monday, 10))
    first = book(new_client(app), slug, body)
    again = book(new_client(app), slug, body)  # doppio clic: stessa chiave
    assert first.status_code == 201 and again.status_code == 201
    assert first.json()["code"] == again.json()["code"]
    other = book(new_client(app), slug, booking(st, start=at(st.monday, 10)))
    assert other.status_code == 409
    day = {"from": at(st.monday, 0), "to": at(st.monday + timedelta(days=1), 0)}
    assert len(st.c.get(f"{API}/appointments", params=day).json()) == 1


def test_any_professional_picks_who_is_free(app: FastAPI) -> None:
    st, slug = open_studio(app)
    elena = st.c.post(f"{API}/professionals", json={"name": "Elena Rossi"}).json()["id"]
    st.c.put(
        f"{API}/professionals/{elena}/availability",
        json={
            "rules": [
                {"weekday": d, "start_time": "09:00", "end_time": "13:00"} for d in range(1, 6)
            ]
        },
    )
    st.c.patch(
        f"{API}/services/{st.services['Controllo']['id']}",
        json={"professional_ids": [st.prof, elena]},
    )
    st.book(at(st.monday, 10))  # la titolare è occupata alle 10
    d = st.monday.isoformat()
    slot = next(
        x
        for x in new_client(app)
        .get(
            f"{API}/public/studios/{slug}/slots",
            params={"service_id": st.services["Controllo"]["id"], "from": d, "to": d},
        )
        .json()["days"][d]
        if x["time"] == "10:00"
    )
    assert slot["professional_ids"] == [elena]
    r = book(new_client(app), slug, booking(st, start=at(st.monday, 10)))
    assert r.status_code == 201 and r.json()["professional"] == "Elena Rossi"


def test_manual_confirmation_setting(app: FastAPI) -> None:
    st, slug = open_studio(app, online_booking_requires_confirmation=True)
    email = unique_email("attesa")
    r = book(new_client(app), slug, booking(st, start=at(st.monday, 9), email=email))
    assert r.json()["status"] == "pending"
    assert any(m.to == email and "da confermare" in m.subject.lower() for m in MEMORY_OUTBOX)


def test_spam_guards_and_limits(app: FastAPI) -> None:
    st, slug = open_studio(app)
    guest = new_client(app)
    r = book(guest, slug, booking(st, start=at(st.monday, 9), website="http://spam.example"))
    assert r.status_code == 422
    r = book(guest, slug, booking(st, start=at(st.monday, 9), privacy_accepted=False))
    assert r.status_code == 422
    r = book(guest, slug, booking(st, start=at(st.monday, 9), phone="abc def"))
    assert r.status_code == 422
    email = unique_email("tante")
    codes = [
        book(
            guest, slug, booking(st, start=at(st.monday, 9 + i // 2, (i % 2) * 30), email=email)
        ).status_code
        for i in range(6)
    ]
    assert codes[:5] == [201] * 5 and codes[5] == 429


def test_suspended_studio_page_disappears(app: FastAPI, owner_engine: Engine) -> None:
    _, slug = open_studio(app)
    sql(owner_engine, "UPDATE tenants SET status = 'suspended' WHERE slug = :s", s=slug)
    assert new_client(app).get(f"{API}/public/studios/{slug}").status_code == 404


def test_public_pages_are_isolated(app: FastAPI) -> None:
    a, slug_a = open_studio(app, "Studio A")
    b, _ = open_studio(app, "Studio B")
    r = book(
        new_client(app),
        slug_a,
        booking(a, start=at(a.monday, 9), service_id=b.services["Controllo"]["id"]),
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "prestazione_non_valida"
    r = new_client(app).get(
        f"{API}/public/studios/{slug_a}/slots",
        params={
            "service_id": a.services["Controllo"]["id"],
            "professional_id": b.prof,
            "from": a.monday.isoformat(),
            "to": a.monday.isoformat(),
        },
    )
    assert r.status_code == 422
