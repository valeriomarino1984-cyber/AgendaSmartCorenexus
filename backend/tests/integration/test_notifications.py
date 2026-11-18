"""Notifiche email ai clienti: conferme, promemoria, spostamenti, annullamenti, regole e cron."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy import Engine

from app.core.config import Settings
from app.main import create_app
from app.modules.email import sender
from app.modules.email.sender import MEMORY_OUTBOX
from app.modules.notifications import service as notifications
from tests.integration.conftest import new_client
from tests.integration.test_accounts import last_token, sql, unique_email
from tests.integration.test_agenda import Studio, at

API = "/api/v1"
CRON_KEY = "chiave-del-cron-di-prova-123456"


@pytest.fixture
def napp(settings: Settings) -> Iterator[FastAPI]:
    application = create_app(settings.model_copy(update={"cron_secret": SecretStr(CRON_KEY)}))
    yield application
    application.state.db.dispose()


def client_with_email(st: Studio, *, consent: bool = True, **extra: object) -> tuple[str, str]:
    email = unique_email("cliente")
    r = st.c.post(
        f"{API}/clients",
        json={
            "first_name": "Giulia",
            "last_name": "Ferri",
            "email": email,
            "email_consent": consent,
            **extra,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"], email


def mails_to(email: str) -> list[sender.OutgoingEmail]:
    return [m for m in MEMORY_OUTBOX if m.to == email]


def jobs(st: Studio, appointment_id: str) -> list[tuple[str, str]]:
    detail = st.c.get(f"{API}/appointments/{appointment_id}").json()
    return [(n["kind"], n["status"]) for n in detail["notifications"]]


def test_confirmation_sent_and_reminder_scheduled(napp: FastAPI) -> None:
    st = Studio(napp, "Studio Conferme")
    st.c.put(
        f"{API}/tenants/current",
        json={"contact_email": "segreteria@studio.example", "contact_phone": "+39 02 1234567"},
    )
    cid, email = client_with_email(st)
    a = st.book(at(st.monday, 10), client_id=cid).json()

    mail = mails_to(email)[-1]
    assert mail.subject == "Appuntamento confermato · Studio Conferme"
    assert (
        mail.from_name == "Studio Conferme via Agenda"
        and mail.reply_to == "segreteria@studio.example"
    )
    assert (
        "alle 10:00" in mail.text and "/area-clienti" in mail.text and "+39 02 1234567" in mail.text
    )
    assert sorted(jobs(st, a["id"])) == [("confirmation", "sent"), ("reminder", "pending")]
    reminder = next(
        n
        for n in st.c.get(f"{API}/appointments/{a['id']}").json()["notifications"]
        if n["kind"] == "reminder"
    )
    assert reminder["scheduled_at"] < a["start_at"]  # 24 ore prima


def test_neutral_text_and_online_link(napp: FastAPI) -> None:
    st = Studio(napp, "Studio Discreto")  # nutrizionista: messaggi discreti attivi
    cid, email = client_with_email(st)
    a = st.book(at(st.monday, 9), "Controllo online", client_id=cid).json()
    mail = mails_to(email)[-1]
    assert "Controllo" not in mail.text and "Appuntamento con" in mail.text
    assert a["video_url"] in (mail.html or "") and "Entra nella videochiamata" in (mail.html or "")

    st.c.put(f"{API}/tenants/current", json={"neutral_messaging": False})
    st.book(at(st.monday, 11), client_id=cid)
    assert "Controllo con" in mails_to(email)[-1].text


def test_no_consent_or_no_messages_are_skipped_and_retry(napp: FastAPI) -> None:
    st = Studio(napp)
    cid, email = client_with_email(st, consent=False)
    a = st.book(at(st.monday, 9), client_id=cid).json()
    assert mails_to(email) == []
    detail = st.c.get(f"{API}/appointments/{a['id']}").json()["notifications"]
    conf = next(n for n in detail if n["kind"] == "confirmation")
    assert conf["status"] == "skipped" and conf["reason"] == "senza_consenso"
    assert conf["reason_label"] == "Manca il consenso ai promemoria via email"

    st.c.patch(f"{API}/clients/{cid}", json={"email_consent": True})
    r = st.c.post(f"{API}/notifications/{conf['id']}/retry")
    assert r.status_code == 201
    assert len(mails_to(email)) == 1
    r = st.c.post(
        f"{API}/notifications/{conf['id']}/retry"
    )  # quello vecchio resta "saltato": ammesso
    sent = next(n for n in st.c.get(f"{API}/notifications").json() if n["status"] == "sent")
    r = st.c.post(f"{API}/notifications/{sent['id']}/retry")
    assert r.status_code == 409 and r.json()["error"]["code"] == "non_ritentabile"

    cid2, email2 = client_with_email(st, preferred_channel="none")
    a2 = st.book(at(st.monday, 11), client_id=cid2).json()
    assert mails_to(email2) == []
    assert ("confirmation", "skipped") in jobs(st, a2["id"])

    cid3 = st.c.post(f"{API}/clients", json={"first_name": "Senza", "last_name": "Email"}).json()[
        "id"
    ]
    a3 = st.book(at(st.monday, 12), client_id=cid3).json()
    reasons = [
        n["reason"]
        for n in st.c.get(f"{API}/appointments/{a3['id']}").json()["notifications"]
        if n["status"] == "skipped"
    ]
    assert reasons == ["senza_email"]


def test_reschedule_and_cancel(napp: FastAPI) -> None:
    st = Studio(napp)
    cid, email = client_with_email(st)
    a = st.book(at(st.monday, 9), client_id=cid).json()
    r = st.c.patch(
        f"{API}/appointments/{a['id']}",
        json={"version": 1, "start_at": at(st.monday + timedelta(days=1), 11)},
    )
    assert r.status_code == 200
    assert mails_to(email)[-1].subject.startswith("Appuntamento spostato")
    assert "martedì" in mails_to(email)[-1].text and "alle 11:00" in mails_to(email)[-1].text
    kinds = jobs(st, a["id"])
    assert ("reminder", "cancelled") in kinds and ("reminder", "pending") in kinds

    r = st.c.post(
        f"{API}/appointments/{a['id']}/status", json={"version": 2, "status": "cancelled_by_staff"}
    )
    assert r.status_code == 200
    assert mails_to(email)[-1].subject.startswith("Appuntamento annullato")
    assert ("reminder", "pending") not in jobs(st, a["id"])
    assert ("cancelled", "sent") in jobs(st, a["id"])


def test_client_cancel_from_portal_sends_notice(napp: FastAPI) -> None:
    st = Studio(napp)
    cid, email = client_with_email(st)
    a = st.book(at(st.monday, 9), client_id=cid).json()
    c = new_client(napp)
    c.post(f"{API}/client-portal/link", json={"email": email})
    c.post(f"{API}/client-portal/login", json={"token": last_token("/area-clienti/entra")})
    assert c.post(f"{API}/client-portal/appointments/{a['id']}/cancel").status_code == 204
    assert mails_to(email)[-1].subject.startswith("Appuntamento annullato")
    assert ("reminder", "cancelled") in jobs(st, a["id"])


def test_cron_sends_due_reminders(napp: FastAPI, owner_engine: Engine) -> None:
    st = Studio(napp)
    cid, email = client_with_email(st)
    a = st.book(at(st.monday, 9), client_id=cid).json()
    sql(
        owner_engine,
        "UPDATE notification_jobs SET scheduled_at = UTC_TIMESTAMP() - INTERVAL 1 MINUTE "
        "WHERE kind = 'reminder' AND status = 'pending' AND appointment_id = :a",
        a=a["id"].replace("-", ""),
    )
    cron = new_client(napp)
    assert cron.post(f"{API}/webhooks/cron/notifiche").status_code == 403
    assert (
        cron.post(f"{API}/webhooks/cron/notifiche", headers={"X-Cron-Key": "sbagliata"}).status_code
        == 403
    )
    r = cron.post(f"{API}/webhooks/cron/notifiche", headers={"X-Cron-Key": CRON_KEY, "Origin": ""})
    assert r.status_code == 200 and r.json()["sent"] >= 1
    assert mails_to(email)[-1].subject.startswith("Promemoria:")
    assert ("reminder", "sent") in jobs(st, a["id"])


def test_cron_is_off_without_key(app: FastAPI) -> None:
    assert (
        new_client(app)
        .post(f"{API}/webhooks/cron/notifiche", headers={"X-Cron-Key": "x"})
        .status_code
        == 404
    )


def test_studio_settings_turn_messages_off(napp: FastAPI) -> None:
    st = Studio(napp)
    r = st.c.put(f"{API}/tenants/current", json={"email_confirmations": False, "reminder_hours": 0})
    assert r.status_code == 200 and r.json()["reminder_hours"] == 0
    cid, email = client_with_email(st)
    a = st.book(at(st.monday, 9), client_id=cid).json()
    assert jobs(st, a["id"]) == [] and mails_to(email) == []

    st.c.put(f"{API}/tenants/current", json={"email_confirmations": False, "reminder_hours": 48})
    a2 = st.book(at(st.monday, 11), client_id=cid).json()
    assert jobs(st, a2["id"]) == [("reminder", "pending")]


def test_smtp_failures_are_retried_then_marked_failed(
    napp: FastAPI, owner_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    st = Studio(napp)
    cid, _ = client_with_email(st)
    monkeypatch.setattr(notifications, "send_email", lambda settings, mail: False)
    a = st.book(at(st.monday, 9), client_id=cid).json()
    conf = next(
        n
        for n in st.c.get(f"{API}/appointments/{a['id']}").json()["notifications"]
        if n["kind"] == "confirmation"
    )
    assert (
        conf["status"] == "pending" and conf["attempts"] == 1 and conf["reason"] == "errore_invio"
    )
    for _ in range(2):
        sql(
            owner_engine,
            "UPDATE notification_jobs SET scheduled_at = UTC_TIMESTAMP() "
            "WHERE kind='confirmation' AND status='pending'",
        )
        notifications.process_due(napp.state.db, napp.state.settings)
    conf = next(
        n
        for n in st.c.get(f"{API}/appointments/{a['id']}").json()["notifications"]
        if n["kind"] == "confirmation"
    )
    assert conf["status"] == "failed" and conf["attempts"] == 3
    assert (
        next(n for n in st.c.get(f"{API}/notifications").json() if n["id"] == conf["id"])[
            "status_label"
        ]
        == "Non riuscita"
    )


def test_parallel_processing_sends_once(
    napp: FastAPI, owner_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    st = Studio(napp)
    cid, email = client_with_email(st)
    st.c.put(f"{API}/tenants/current", json={"email_confirmations": False, "reminder_hours": 48})
    a = st.book(at(st.monday, 9), client_id=cid).json()
    sql(
        owner_engine,
        "UPDATE notification_jobs SET scheduled_at = UTC_TIMESTAMP() - INTERVAL 1 MINUTE "
        "WHERE status = 'pending'",
    )
    real = sender.send_email
    started = threading.Barrier(4)

    def slow_send(settings: Settings, mail: sender.OutgoingEmail) -> bool:
        return real(settings, mail)

    monkeypatch.setattr(notifications, "send_email", slow_send)

    def worker() -> None:
        started.wait()
        notifications.process_due(napp.state.db, napp.state.settings)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(mails_to(email)) == 1
    assert ("reminder", "sent") in jobs(st, a["id"])


def test_notifications_are_isolated_between_studios(napp: FastAPI) -> None:
    a, b = Studio(napp, "Studio A"), Studio(napp, "Studio B")
    cid, _ = client_with_email(a, consent=False)
    a.book(at(a.monday, 9), client_id=cid)
    job = a.c.get(f"{API}/notifications").json()[0]
    assert b.c.get(f"{API}/notifications").json() == []
    assert b.c.post(f"{API}/notifications/{job['id']}/retry").status_code == 404
    assert new_client(napp).get(f"{API}/notifications").status_code == 401


def test_professional_sees_only_own_notifications(napp: FastAPI) -> None:
    from tests.integration.test_catalog import invite_and_join

    st = Studio(napp)
    pro = invite_and_join(st.c, "professional", "Luca Moretti")
    luca = next(
        p["id"] for p in st.c.get(f"{API}/professionals").json() if p["name"] == "Luca Moretti"
    )
    st.c.patch(
        f"{API}/services/{st.services['Controllo']['id']}",
        json={"professional_ids": [st.prof, luca]},
    )
    cid, _ = client_with_email(st, consent=False)
    st.book(at(st.monday, 9), client_id=cid)
    st.book(at(st.monday, 15), client_id=cid, professional_id=luca, force=True)
    # Ogni appuntamento ha conferma e promemoria: 4 in tutto, 2 sono di Luca.
    assert len(st.c.get(f"{API}/notifications").json()) == 4
    mine = pro.get(f"{API}/notifications").json()
    assert len(mine) == 2 and {n["kind"] for n in mine} == {"confirmation", "reminder"}
