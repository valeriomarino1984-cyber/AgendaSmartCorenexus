"""Area piattaforma: prima configurazione, password + codice, studi, personale, registro."""

from __future__ import annotations

import base64
import time
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine

from app.core.config import Settings
from app.main import create_app
from app.modules.email.sender import MEMORY_OUTBOX
from app.modules.platform.totp import code_at
from tests.integration.conftest import new_client
from tests.integration.test_accounts import PASSWORD, last_token, signup_verified, sql, unique_email

API = "/api/v1/platform"
KEY = "chiave-di-prova-della-piattaforma-0123456789"
BOOT = "fondatore@corenexus.example"
STAFF_PASSWORD = "Piattaforma-sicura-2026"


@pytest.fixture
def papp(settings: Settings, owner_engine: Engine) -> Iterator[FastAPI]:
    # Il database dei test conserva i dati: si riparte da un'area piattaforma vuota.
    sql(owner_engine, "DELETE FROM platform_sessions")
    sql(owner_engine, "DELETE FROM platform_tokens")
    sql(owner_engine, "DELETE FROM platform_staff")
    conf = settings.model_copy(
        update={"platform_secret_key": SecretStr(KEY), "platform_bootstrap_email": BOOT}
    )
    application = create_app(conf)
    yield application
    application.state.db.dispose()


def secret_from(info: dict[str, object]) -> bytes:
    b32 = str(info["secret"])
    return base64.b32decode(b32 + "=" * (-len(b32) % 8))


def code(secret: bytes, offset: int = 0) -> str:
    return code_at(secret, int(time.time() // 30) + offset)


def bootstrap(app: FastAPI) -> tuple[TestClient, bytes]:
    c = new_client(app)
    assert c.get(f"{API}/status").json() == {"configured": True, "setup_available": True}
    assert c.post(f"{API}/setup", json={"email": BOOT}).status_code == 202
    token = last_token("/piattaforma/invito")
    info = c.get(f"{API}/invite", params={"token": token}).json()
    secret = secret_from(info)
    r = c.post(
        f"{API}/invite/accept",
        json={
            "token": token,
            "full_name": "Valeria Fondatrice",
            "password": STAFF_PASSWORD,
            "code": code(secret),
        },
    )
    assert r.status_code == 200, r.text
    return c, secret


def test_area_is_off_without_key(app: FastAPI) -> None:
    c = new_client(app)
    assert c.get(f"{API}/status").json()["configured"] is False
    r = c.post(f"{API}/login", json={"email": BOOT, "password": "x"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "piattaforma_spenta"


def test_bootstrap_only_for_configured_email_and_only_once(papp: FastAPI) -> None:
    c = new_client(papp)
    MEMORY_OUTBOX.clear()
    c.post(f"{API}/setup", json={"email": "intruso@example.com"})
    assert MEMORY_OUTBOX == []  # stessa risposta, nessuna email

    c.post(f"{API}/setup", json={"email": BOOT})
    token = last_token("/piattaforma/invito")
    info = c.get(f"{API}/invite", params={"token": token}).json()
    assert info["otpauth_uri"].startswith("otpauth://totp/CoreNexus%20Agenda%3A")
    secret = secret_from(info)

    body = {"token": token, "full_name": "Valeria", "password": STAFF_PASSWORD, "code": "000000"}
    r = c.post(f"{API}/invite/accept", json=body)
    assert r.status_code == 401 and r.json()["error"]["code"] == "codice_errato"
    r = c.post(f"{API}/invite/accept", json={**body, "password": "corta", "code": code(secret)})
    assert r.status_code == 422 and r.json()["error"]["code"] == "password_debole"
    r = c.post(f"{API}/invite/accept", json={**body, "code": code(secret)})
    assert r.status_code == 200 and r.json()["email"] == BOOT
    assert c.get(f"{API}/me").status_code == 200
    assert "agenda_piattaforma" in c.cookies

    # Link monouso e configurazione non più disponibile.
    r = c.get(f"{API}/invite", params={"token": token})
    assert r.status_code == 422 and r.json()["error"]["code"] == "link_non_valido"
    assert c.get(f"{API}/status").json()["setup_available"] is False
    MEMORY_OUTBOX.clear()
    c.post(f"{API}/setup", json={"email": BOOT})
    assert MEMORY_OUTBOX == []


def test_login_requires_password_and_code(papp: FastAPI) -> None:
    _, secret = bootstrap(papp)
    c = new_client(papp)
    r = c.post(f"{API}/login", json={"email": BOOT, "password": "sbagliata"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "credenziali_errate"

    assert c.post(f"{API}/login", json={"email": BOOT, "password": STAFF_PASSWORD}).json() == {
        "mfa_required": True
    }
    assert c.get(f"{API}/me").status_code == 401  # solo password: non basta
    assert c.get(f"{API}/tenants").status_code == 401
    r = c.post(f"{API}/login/mfa", json={"code": "123456"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "codice_errato"
    used = code(secret, 1)
    assert c.post(f"{API}/login/mfa", json={"code": used}).status_code == 200
    assert c.get(f"{API}/me").json()["full_name"] == "Valeria Fondatrice"

    # Lo stesso codice non vale una seconda volta.
    other = new_client(papp)
    other.post(f"{API}/login", json={"email": BOOT, "password": STAFF_PASSWORD})
    r = other.post(f"{API}/login/mfa", json={"code": used})
    assert r.status_code == 401


def test_too_many_wrong_codes_close_the_attempt(papp: FastAPI) -> None:
    _, secret = bootstrap(papp)
    c = new_client(papp)
    c.post(f"{API}/login", json={"email": BOOT, "password": STAFF_PASSWORD})
    for _ in range(5):
        c.post(f"{API}/login/mfa", json={"code": "000000"})
    r = c.post(f"{API}/login/mfa", json={"code": code(secret, 1)})
    assert r.status_code == 401 and r.json()["error"]["code"] == "non_autenticato"


def test_session_closes_after_30_idle_minutes(papp: FastAPI, owner_engine: Engine) -> None:
    c, _ = bootstrap(papp)
    sql(
        owner_engine,
        "UPDATE platform_sessions SET last_seen_at = UTC_TIMESTAMP() - INTERVAL 31 MINUTE",
    )
    assert c.get(f"{API}/me").status_code == 401


def test_areas_are_separate(papp: FastAPI) -> None:
    staff, _ = bootstrap(papp)
    studio = new_client(papp)
    signup_verified(studio)
    assert studio.get(f"{API}/tenants").status_code == 401
    assert studio.get(f"{API}/me").status_code == 401
    assert staff.get("/api/v1/clients").status_code == 401
    assert staff.get("/api/v1/auth/me").status_code == 401


def test_create_tenant_invites_owner_and_manage_it(papp: FastAPI) -> None:
    staff, _ = bootstrap(papp)
    owner_email = unique_email("titolare")
    r = staff.post(
        f"{API}/tenants",
        json={
            "name": "Studio Osteopatia Neri",
            "business_type": "osteopata",
            "owner_name": "Paolo Neri",
            "owner_email": owner_email,
            "trial_days": 30,
        },
    )
    assert r.status_code == 201, r.text
    tenant = r.json()
    assert tenant["status"] == "trial" and tenant["owner_invitation_pending"] is True
    assert tenant["professionals"] == 1 and tenant["services"] == 2  # profilo osteopata
    assert tenant["email_sent"] is True

    # Il titolare accetta l'invito dalla pagina già esistente.
    owner = new_client(papp)
    r = owner.post(
        "/api/v1/auth/invitation/accept",
        json={"token": last_token("/invito"), "password": PASSWORD},
    )
    assert r.status_code == 200 and r.json()["role"] == "owner"
    assert owner.get("/api/v1/tenants/current").json()["name"] == "Studio Osteopatia Neri"
    owner.post("/api/v1/clients", json={"first_name": "Marta", "last_name": "Gallo"})

    listed = next(
        t
        for t in staff.get(f"{API}/tenants", params={"q": "Osteopatia Neri"}).json()
        if t["id"] == tenant["id"]
    )
    assert listed["clients"] == 1 and listed["owner_invitation_pending"] is False
    # Solo conteggi: nessun nome di cliente nelle risposte della piattaforma.
    assert "Marta" not in str(staff.get(f"{API}/tenants/{tenant['id']}").json())

    # Sospensione: il titolare non entra più; riattivazione: di nuovo dentro.
    r = staff.patch(f"{API}/tenants/{tenant['id']}", json={"status": "suspended"})
    assert r.status_code == 200 and r.json()["status"] == "suspended"
    assert owner.get("/api/v1/auth/me").status_code == 401
    staff.patch(f"{API}/tenants/{tenant['id']}", json={"status": "active"})
    assert owner.get("/api/v1/auth/me").status_code == 200

    # Prova estesa e cambio di profilo con prestazioni consigliate.
    before = tenant["trial_ends_at"]
    after = staff.patch(f"{API}/tenants/{tenant['id']}", json={"extend_trial_days": 15}).json()[
        "trial_ends_at"
    ]
    assert after > before
    staff.patch(f"{API}/tenants/{tenant['id']}", json={"business_type": "nutrizionista"})
    assert staff.post(f"{API}/tenants/{tenant['id']}/profile").json() == {
        "profile": "nutrizionista",
        "created": 3,
    }

    r = staff.post(f"{API}/tenants/{tenant['id']}/resend-invite")
    assert r.status_code == 409 and r.json()["error"]["code"] == "gia_attivo"

    actions = [a["action"] for a in staff.get(f"{API}/activity").json()]
    for expected in (
        "tenant_created",
        "tenant_updated",
        "tenant_profile_loaded",
        "login",
        "invite_accepted",
    ):
        if expected != "login":
            assert expected in actions, expected


def test_existing_user_becomes_owner_without_new_password(papp: FastAPI) -> None:
    staff, _ = bootstrap(papp)
    c = new_client(papp)
    email, _ = signup_verified(c, "Studio Esistente")
    MEMORY_OUTBOX.clear()
    r = staff.post(
        f"{API}/tenants",
        json={
            "name": "Secondo Studio",
            "business_type": "psicologo",
            "owner_name": "Anna",
            "owner_email": email,
        },
    )
    assert r.status_code == 201 and r.json()["owner_invitation_pending"] is False
    assert "Ora fai parte di" in MEMORY_OUTBOX[-1].subject
    assert {t["name"] for t in c.get("/api/v1/auth/me").json()["tenants"]} >= {
        "Studio Esistente",
        "Secondo Studio",
    }


def test_staff_invite_and_disable(papp: FastAPI) -> None:
    staff, _ = bootstrap(papp)
    me_id = staff.get(f"{API}/me").json()["id"]
    r = staff.post(
        f"{API}/staff", json={"email": "collega@corenexus.example", "full_name": "Luca Collega"}
    )
    assert r.status_code == 201
    guest = new_client(papp)
    token = last_token("/piattaforma/invito")
    secret = secret_from(guest.get(f"{API}/invite", params={"token": token}).json())
    guest.post(
        f"{API}/invite/accept",
        json={
            "token": token,
            "full_name": "Luca Collega",
            "password": "Tramonto-blu-sul-mare-4",
            "code": code(secret),
        },
    )
    assert guest.get(f"{API}/me").status_code == 200

    people = staff.get(f"{API}/staff").json()
    luca = next(p for p in people if p["email"] == "collega@corenexus.example")
    assert luca["status"] == "active"
    r = staff.patch(f"{API}/staff/{me_id}", json={"status": "disabled"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "se_stesso"
    assert staff.patch(f"{API}/staff/{luca['id']}", json={"status": "disabled"}).status_code == 204
    assert guest.get(f"{API}/me").status_code == 401  # sessioni chiuse subito
    r = staff.post(f"{API}/staff", json={"email": "collega@corenexus.example", "full_name": "Luca"})
    assert r.status_code == 409


def test_production_requires_long_key() -> None:
    with pytest.raises(ValueError, match="almeno 32"):
        Settings(
            environment="production",
            app_base_url="https://agenda.example",
            public_booking_base_url="https://agenda.example/prenota",
            email_backend="smtp",
            smtp_host="smtp.example",
            database_url="mysql+pymysql://a:b@h/d",
            platform_secret_key="corta",
        )


def test_disabled_account_is_out_even_with_open_session(
    papp: FastAPI, owner_engine: Engine
) -> None:
    c, _ = bootstrap(papp)
    # Disattivazione fatta direttamente nel database: la sessione aperta non deve più valere.
    sql(owner_engine, "UPDATE platform_staff SET status = 'disabled'")
    assert c.get(f"{API}/me").status_code == 401
    r = new_client(papp).post(f"{API}/login", json={"email": BOOT, "password": STAFF_PASSWORD})
    assert r.status_code == 401
