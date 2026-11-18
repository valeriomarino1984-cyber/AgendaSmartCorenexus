"""Area clienti: link via email, sessione separata dallo staff, appuntamenti, disdetta."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.modules.email.sender import MEMORY_OUTBOX
from tests.integration.conftest import new_client
from tests.integration.test_accounts import last_token, sql, unique_email
from tests.integration.test_agenda import Studio, at

API = "/api/v1"
LINK = "/area-clienti/entra"
# Indirizzi diversi a ogni esecuzione: il database dei test conserva i dati tra un giro e l'altro.
E_ALTRO = unique_email("altro")
E_ARCHIVIATO = unique_email("archiviato")
E_BREVE = unique_email("breve")
E_GIULIA_CLIENTE = unique_email("giulia.cliente")
E_LIMITE = unique_email("limite")
E_MONOUSO = unique_email("monouso")
E_MULTI = unique_email("multi")
E_SEPARATI = unique_email("separati")


def with_client(st: Studio, email: str, first: str = "Giulia") -> str:
    r = st.c.post(
        f"{API}/clients", json={"first_name": first, "last_name": "Ferri", "email": email}
    )
    assert r.status_code == 201, r.text
    cid: str = r.json()["id"]
    return cid


def client_login(app: FastAPI, email: str) -> TestClient:
    c = new_client(app)
    r = c.post(f"{API}/client-portal/link", json={"email": email})
    assert r.status_code == 202, r.text
    r = c.post(f"{API}/client-portal/login", json={"token": last_token(LINK)})
    assert r.status_code == 200, r.text
    return c


def test_unknown_email_same_answer_and_no_email(app: FastAPI) -> None:
    c = new_client(app)
    r = c.post(f"{API}/client-portal/link", json={"email": unique_email("nessuno")})
    assert r.status_code == 202 and "Se l'indirizzo è registrato" in r.json()["message"]
    assert MEMORY_OUTBOX == []


def test_client_sees_appointments_with_video_link_and_cancels(app: FastAPI) -> None:
    st = Studio(app, "Studio Nutrizione Verdi")
    st.client_id = with_client(st, E_GIULIA_CLIENTE)
    online = st.book(at(st.monday, 9), "Controllo online").json()
    st.book(at(st.monday + timedelta(days=1), 10))

    c = client_login(app, E_GIULIA_CLIENTE.upper())  # maiuscole indifferenti
    mail = MEMORY_OUTBOX[-1]
    assert mail.to == E_GIULIA_CLIENTE and "Studio Nutrizione Verdi" in mail.text
    cookie_names = set(c.cookies.keys())
    assert cookie_names == {"agenda_cliente"}

    me = c.get(f"{API}/client-portal/me").json()
    assert me["email"] == E_GIULIA_CLIENTE
    first = me["upcoming"][0]
    assert first["studio"] == "Studio Nutrizione Verdi" and first["service"] == "Controllo online"
    assert first["video_url"] == online["video_url"] and first["can_cancel"] is True
    assert len(me["upcoming"]) == 2 and me["past"] == []

    assert c.post(f"{API}/client-portal/appointments/{online['id']}/cancel").status_code == 204
    detail = st.c.get(f"{API}/appointments/{online['id']}").json()
    assert detail["status"] == "cancelled_by_client"
    assert detail["events"][-1]["actor_type"] == "client"
    me = c.get(f"{API}/client-portal/me").json()
    cancelled = next(a for a in me["upcoming"] if a["id"] == online["id"])
    assert cancelled["status"] == "cancelled_by_client" and cancelled["video_url"] is None
    r = c.post(f"{API}/client-portal/appointments/{online['id']}/cancel")
    assert r.status_code == 409 and r.json()["error"]["code"] == "appuntamento_chiuso"


def test_cancellation_notice_is_respected(app: FastAPI) -> None:
    st = Studio(app)
    st.client_id = with_client(st, E_BREVE)
    soon = (datetime.now(UTC) + timedelta(hours=2)).replace(second=0, microsecond=0)
    appt = st.book(soon.isoformat(), force=True).json()  # preavviso dello studio: 24 ore
    c = client_login(app, E_BREVE)
    item = c.get(f"{API}/client-portal/me").json()["upcoming"][0]
    assert item["can_cancel"] is False and item["cancellation_min_hours"] == 24
    r = c.post(f"{API}/client-portal/appointments/{appt['id']}/cancel")
    assert r.status_code == 409 and r.json()["error"]["code"] == "preavviso_insufficiente"
    assert st.c.get(f"{API}/appointments/{appt['id']}").json()["status"] == "confirmed"

    st.c.put(f"{API}/tenants/current", json={"cancellation_min_hours": 0})
    assert c.post(f"{API}/client-portal/appointments/{appt['id']}/cancel").status_code == 204


def test_link_is_single_use_and_expires(app: FastAPI, owner_engine: Engine) -> None:
    st = Studio(app)
    st.client_id = with_client(st, E_MONOUSO)
    c = new_client(app)
    c.post(f"{API}/client-portal/link", json={"email": E_MONOUSO})
    token = last_token(LINK)
    assert c.post(f"{API}/client-portal/login", json={"token": token}).status_code == 200
    r = new_client(app).post(f"{API}/client-portal/login", json={"token": token})
    assert r.status_code == 400 and r.json()["error"]["code"] == "link_non_valido"

    c.post(f"{API}/client-portal/link", json={"email": E_MONOUSO})
    late = last_token(LINK)
    sql(
        owner_engine,
        "UPDATE client_login_tokens SET expires_at = UTC_TIMESTAMP() - INTERVAL 1 MINUTE "
        "WHERE email = :e AND used_at IS NULL",
        e=E_MONOUSO,
    )
    assert (
        new_client(app).post(f"{API}/client-portal/login", json={"token": late}).status_code == 400
    )
    rows = sql(
        owner_engine, "SELECT COUNT(*) FROM client_login_tokens WHERE token_hash = :t", t=late
    )
    assert rows[0][0] == 0  # nel database c'è solo l'hash, mai il token


def test_staff_and_client_sessions_are_separate(app: FastAPI) -> None:
    st = Studio(app)
    st.client_id = with_client(st, E_SEPARATI)
    c = client_login(app, E_SEPARATI)
    # Il cliente non entra nell'area dello studio…
    assert c.get(f"{API}/auth/me").status_code == 401
    assert c.get(f"{API}/clients").status_code == 401
    # …e lo staff non entra nell'area clienti.
    assert st.c.get(f"{API}/client-portal/me").status_code == 401
    assert new_client(app).get(f"{API}/client-portal/me").status_code == 401

    assert c.post(f"{API}/client-portal/logout").status_code == 204
    assert c.get(f"{API}/client-portal/me").status_code == 401


def test_client_sees_only_own_appointments_across_studios(app: FastAPI) -> None:
    a, b = Studio(app, "Studio A"), Studio(app, "Studio B")
    a.client_id = with_client(a, E_MULTI)
    b.client_id = with_client(b, E_MULTI)
    appt_a = a.book(at(a.monday, 9)).json()
    appt_b = b.book(at(b.monday, 10)).json()
    other_id = with_client(a, E_ALTRO, "Marco")
    other = a.book(at(a.monday, 11), client_id=other_id).json()
    archived_id = with_client(b, E_ARCHIVIATO, "Sara")
    b.book(at(b.monday, 12), client_id=archived_id)
    b.c.delete(f"{API}/clients/{archived_id}")

    c = client_login(app, E_MULTI)
    me = c.get(f"{API}/client-portal/me").json()
    assert {x["studio"] for x in me["upcoming"]} == {"Studio A", "Studio B"}
    assert {x["id"] for x in me["upcoming"]} == {appt_a["id"], appt_b["id"]}
    # L'appuntamento di un altro cliente non si vede e non si disdice.
    r = c.post(f"{API}/client-portal/appointments/{other['id']}/cancel")
    assert r.status_code == 404
    assert a.c.get(f"{API}/appointments/{other['id']}").json()["status"] == "confirmed"

    # Cliente archiviato: nessun link.
    MEMORY_OUTBOX.clear()
    new_client(app).post(f"{API}/client-portal/link", json={"email": E_ARCHIVIATO})
    assert MEMORY_OUTBOX == []


def test_link_requests_are_rate_limited(app: FastAPI) -> None:
    st = Studio(app)
    st.client_id = with_client(st, E_LIMITE)
    c = new_client(app)
    for _ in range(5):
        assert c.post(f"{API}/client-portal/link", json={"email": E_LIMITE}).status_code == 202
    assert len([m for m in MEMORY_OUTBOX if m.to == E_LIMITE]) == 3
