"""Sprint 1: registrazione, verifica, accesso, password, inviti, ruoli, isolamento tra studi."""

from __future__ import annotations

import re
import uuid

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.core.config import Settings
from app.main import create_app
from app.modules.email.sender import MEMORY_OUTBOX
from tests.integration.conftest import new_client

PASSWORD = "Tramonto-sul-lago-7"


def unique_email(prefix: str = "utente") -> str:
    return f"{prefix}.{uuid.uuid4().hex[:10]}@example.com"


def last_token(path: str) -> str:
    """Token dall'ultima email inviata che contiene il link indicato."""
    for mail in reversed(MEMORY_OUTBOX):
        match = re.search(rf"{re.escape(path)}\?token=([A-Za-z0-9_-]+)", mail.text)
        if match:
            return match.group(1)
    raise AssertionError(f"nessuna email con link {path}")


def register(client: TestClient, email: str, studio: str = "Studio Prova", **extra: object) -> None:
    body = {
        "studio_name": studio,
        "business_type": "nutrizionista",
        "full_name": "Anna Bianchi",
        "email": email,
        "password": PASSWORD,
        "accept_terms": True,
        **extra,
    }
    r = client.post("/api/v1/auth/register", json=body)
    assert r.status_code == 202, r.text


def signup_verified(
    client: TestClient, studio: str = "Studio Prova"
) -> tuple[str, dict[str, object]]:
    email = unique_email()
    register(client, email, studio)
    r = client.post("/api/v1/auth/verify-email", json={"token": last_token("/verifica-email")})
    assert r.status_code == 200, r.text
    return email, r.json()


def login(client: TestClient, email: str, password: str = PASSWORD) -> httpx.Response:
    r: httpx.Response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    return r


def sql(engine: Engine, query: str, **params: object) -> list[tuple[object, ...]]:
    with engine.begin() as conn:
        result = conn.execute(text(query), params)
        return [tuple(r) for r in result] if result.returns_rows else []


# ---------------------------------------------------------------- registrazione e verifica


def test_signup_verify_and_me(client: TestClient) -> None:
    email = unique_email()
    register(client, email, "Studio Nutrizione Verdi")
    assert MEMORY_OUTBOX[-1].to == email and "Conferma" in MEMORY_OUTBOX[-1].subject

    r = login(client, email)
    assert r.status_code == 403 and r.json()["error"]["code"] == "email_non_verificata"

    r = client.post("/api/v1/auth/verify-email", json={"token": last_token("/verifica-email")})
    assert r.status_code == 200
    me = r.json()
    assert me["role"] == "owner" and me["role_label"] == "Titolare"
    assert me["tenant"]["name"] == "Studio Nutrizione Verdi"
    assert me["tenant"]["slug"].startswith("studio-nutrizione-verdi")
    assert me["tenant"]["status"] == "trial" and me["tenant"]["trial_ends_at"]
    assert client.get("/api/v1/auth/me").json()["user"]["email"] == email


def test_health_categories_get_neutral_messages(client: TestClient) -> None:
    signup_verified(client)
    assert client.get("/api/v1/tenants/current").json()["neutral_messaging"] is True


def test_duplicate_email_gives_same_answer_and_no_second_studio(
    client: TestClient, owner_engine: Engine
) -> None:
    email, _ = signup_verified(client)
    MEMORY_OUTBOX.clear()
    other = new_client(client.app)  # type: ignore[arg-type]
    r = other.post(
        "/api/v1/auth/register",
        json={
            "studio_name": "Copia",
            "business_type": "psicologo",
            "full_name": "X Y",
            "email": email.upper(),
            "password": PASSWORD,
            "accept_terms": True,
        },
    )
    assert r.status_code == 202
    assert "già un account" in MEMORY_OUTBOX[-1].subject
    assert sql(owner_engine, "SELECT COUNT(*) FROM tenants WHERE name = 'Copia'") == [(0,)]


def test_signup_closed(app: FastAPI, settings: Settings) -> None:
    closed = create_app(settings.model_copy(update={"signup_open": False}))
    try:
        r = new_client(closed).post(
            "/api/v1/auth/register",
            json={
                "studio_name": "Studio X",
                "business_type": "psicologo",
                "full_name": "Anna",
                "email": unique_email(),
                "password": PASSWORD,
                "accept_terms": True,
            },
        )
        assert r.status_code == 403 and r.json()["error"]["code"] == "registrazione_chiusa"
    finally:
        closed.state.db.dispose()


@pytest.mark.parametrize(
    ("override", "code"),
    [
        ({"password": "corta"}, "password_debole"),
        ({"accept_terms": False}, "validation_error"),
        ({"business_type": "astronauta"}, "categoria_non_valida"),
        ({"email": "non-una-email"}, "validation_error"),
    ],
)
def test_signup_validation(client: TestClient, override: dict[str, object], code: str) -> None:
    body = {
        "studio_name": "Studio",
        "business_type": "psicologo",
        "full_name": "Anna Bianchi",
        "email": unique_email(),
        "password": PASSWORD,
        "accept_terms": True,
        **override,
    }
    r = client.post("/api/v1/auth/register", json=body)
    assert r.status_code == 422 and r.json()["error"]["code"] == code


def test_verification_link_is_single_use_and_expires(
    client: TestClient, owner_engine: Engine
) -> None:
    register(client, unique_email())
    token = last_token("/verifica-email")
    assert client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 200
    r = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert r.status_code == 422 and r.json()["error"]["code"] == "link_non_valido"

    register(client, unique_email())
    token = last_token("/verifica-email")
    sql(
        owner_engine, "UPDATE user_tokens SET expires_at = :t WHERE used_at IS NULL", t="2000-01-01"
    )
    assert client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 422


def test_secrets_are_stored_hashed(client: TestClient, owner_engine: Engine) -> None:
    email, _ = signup_verified(client)
    (pw_hash,) = sql(owner_engine, "SELECT password_hash FROM users WHERE email = :e", e=email)[0]
    assert str(pw_hash).startswith("scrypt$") and PASSWORD not in str(pw_hash)
    cookie = client.cookies.get("agenda_session")
    assert cookie and sql(
        owner_engine, "SELECT COUNT(*) FROM auth_sessions WHERE token_hash = :t", t=cookie
    ) == [(0,)]


# ---------------------------------------------------------------- accesso e sessioni


def test_login_logout_and_cookie_flags(client: TestClient) -> None:
    email, _ = signup_verified(client)
    client.cookies.clear()
    r = login(client, email)
    assert r.status_code == 200
    set_cookie = r.headers["set-cookie"].lower()
    assert "httponly" in set_cookie and "samesite=lax" in set_cookie and "path=/" in set_cookie
    assert client.get("/api/v1/auth/me").status_code == 200
    stolen = client.cookies.get("agenda_session")

    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
    # Il vecchio cookie non vale più nemmeno se qualcuno l'ha copiato.
    copy = new_client(client.app)  # type: ignore[arg-type]
    copy.cookies.set("agenda_session", stolen or "")
    assert copy.get("/api/v1/auth/me").status_code == 401


def test_wrong_password_and_lockout(client: TestClient) -> None:
    email, _ = signup_verified(client)
    client.cookies.clear()
    for _ in range(5):
        r = login(client, email, "Password-sbagliata-1")
        assert r.status_code == 401 and r.json()["error"]["code"] == "credenziali_errate"
    r = login(client, email)  # ora anche la password giusta è bloccata per 15 minuti
    assert r.status_code == 429


def test_unknown_email_same_error_as_wrong_password(client: TestClient) -> None:
    r = login(client, unique_email())
    assert r.status_code == 401 and r.json()["error"]["code"] == "credenziali_errate"


def test_idle_session_expires(client: TestClient, owner_engine: Engine) -> None:
    signup_verified(client)
    sql(
        owner_engine,
        "UPDATE auth_sessions SET last_seen_at = :t WHERE revoked_at IS NULL",
        t="2000-01-01",
    )
    assert client.get("/api/v1/auth/me").status_code == 401


def test_staff_session_closes_after_one_idle_hour(client: TestClient, owner_engine: Engine) -> None:
    email, _ = signup_verified(client)
    q = (
        "UPDATE auth_sessions SET last_seen_at = UTC_TIMESTAMP() - INTERVAL {} MINUTE "
        "WHERE revoked_at IS NULL AND user_id = (SELECT id FROM users WHERE email = :e)"
    )
    sql(owner_engine, q.format(50), e=email)
    assert client.get("/api/v1/auth/me").status_code == 200  # 50 minuti: ancora dentro
    sql(owner_engine, q.format(61), e=email)
    assert client.get("/api/v1/auth/me").status_code == 401  # oltre l'ora: fuori


def test_csrf_origin_check(client: TestClient) -> None:
    body = {"email": unique_email(), "password": PASSWORD}
    bare = TestClient(client.app)
    r = bare.post("/api/v1/auth/login", json=body)
    assert r.status_code == 403 and r.json()["error"]["code"] == "origine_non_valida"
    r = bare.post(
        "/api/v1/auth/login", json=body, headers={"Origin": "https://sito-malevolo.example"}
    )
    assert r.status_code == 403
    assert (
        bare.post(
            "/api/v1/auth/login", json=body, headers={"Referer": "http://localhost:3000/accedi"}
        ).status_code
        == 401
    )
    assert bare.get("/api/v1/meta/config").status_code == 200  # le letture non richiedono Origin


# ---------------------------------------------------------------- password


def test_forgot_and_reset_password(client: TestClient) -> None:
    email, _ = signup_verified(client)
    MEMORY_OUTBOX.clear()
    assert client.post("/api/v1/auth/password/forgot", json={"email": email}).status_code == 202
    token = last_token("/reimposta-password")

    r = client.post("/api/v1/auth/password/reset", json={"token": token, "password": "corta"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "password_debole"
    # Il link non è stato consumato dal tentativo con password debole.
    new_password = "Nuova-password-sicura-9"
    assert (
        client.post(
            "/api/v1/auth/password/reset", json={"token": token, "password": new_password}
        ).status_code
        == 200
    )

    assert client.get("/api/v1/auth/me").status_code == 401  # sessioni chiuse dopo il cambio
    assert login(client, email).status_code == 401
    assert login(client, email, new_password).status_code == 200


def test_forgot_unknown_email_sends_nothing(client: TestClient) -> None:
    r = client.post("/api/v1/auth/password/forgot", json={"email": unique_email()})
    assert r.status_code == 202
    assert MEMORY_OUTBOX == []


# ---------------------------------------------------------------- inviti e ruoli


def test_invite_new_collaborator_and_role_limits(client: TestClient) -> None:
    signup_verified(client, "Studio Alfa")
    secretary_email = unique_email("segreteria")
    r = client.post(
        "/api/v1/tenants/current/users",
        json={"email": secretary_email, "full_name": "Sara Galli", "role": "secretary"},
    )
    assert r.status_code == 201 and r.json()["email_sent"] is True
    token = last_token("/invito")

    guest = new_client(client.app)  # type: ignore[arg-type]
    info = guest.get("/api/v1/auth/invitation", params={"token": token}).json()
    assert info == {
        "studio": "Studio Alfa",
        "email": secretary_email,
        "full_name": "Sara Galli",
        "has_password": False,
    }
    r = guest.post(
        "/api/v1/auth/invitation/accept", json={"token": token, "password": "Segreteria-sicura-1"}
    )
    assert r.status_code == 200 and r.json()["role"] == "secretary"

    assert guest.get("/api/v1/tenants/current").status_code == 200
    for method, path, body in [
        ("get", "/api/v1/tenants/current/users", None),
        (
            "post",
            "/api/v1/tenants/current/users",
            {"email": unique_email(), "full_name": "X Y", "role": "owner"},
        ),
        ("put", "/api/v1/tenants/current", {"name": "Rinominato"}),
    ]:
        r = getattr(guest, method)(path, json=body) if body else getattr(guest, method)(path)
        assert r.status_code == 403 and r.json()["error"]["code"] == "ruolo_insufficiente", path

    members = client.get("/api/v1/tenants/current/users").json()
    assert {m["email"] for m in members} >= {secretary_email}
    assert next(m for m in members if m["email"] == secretary_email)["invitation_pending"] is False


def test_invite_existing_user_from_other_studio_and_switch(app: FastAPI) -> None:
    owner_a, owner_b = new_client(app), new_client(app)
    email_a, _ = signup_verified(owner_a, "Studio A")
    signup_verified(owner_b, "Studio B")

    r = owner_b.post(
        "/api/v1/tenants/current/users",
        json={"email": email_a, "full_name": "Anna", "role": "professional"},
    )
    assert r.status_code == 201
    assert "Ora fai parte" in MEMORY_OUTBOX[-1].subject
    r = owner_b.post(
        "/api/v1/tenants/current/users",
        json={"email": email_a, "full_name": "Anna", "role": "professional"},
    )
    assert r.status_code == 409

    tenants = owner_a.get("/api/v1/auth/me").json()["tenants"]
    assert {t["name"] for t in tenants} == {"Studio A", "Studio B"}
    b_id = next(t["id"] for t in tenants if t["name"] == "Studio B")
    me = owner_a.post("/api/v1/auth/switch-tenant", json={"tenant_id": b_id}).json()
    assert me["tenant"]["name"] == "Studio B" and me["role"] == "professional"
    assert owner_a.get("/api/v1/tenants/current/users").status_code == 403  # in B non è titolare


def test_cannot_switch_to_studio_without_membership(app: FastAPI) -> None:
    a, b = new_client(app), new_client(app)
    signup_verified(a, "Studio A")
    _, me_b = signup_verified(b, "Studio B")
    r = a.post("/api/v1/auth/switch-tenant", json={"tenant_id": me_b["tenant"]["id"]})  # type: ignore[index]
    assert r.status_code == 404
    assert a.get("/api/v1/auth/me").json()["tenant"]["name"] == "Studio A"


def test_isolation_between_studios(app: FastAPI) -> None:
    a, b = new_client(app), new_client(app)
    signup_verified(a, "Studio A")
    signup_verified(b, "Studio B")
    a.post(
        "/api/v1/tenants/current/users",
        json={"email": unique_email(), "full_name": "Collab A", "role": "professional"},
    )

    members_a = a.get("/api/v1/tenants/current/users").json()
    members_b = b.get("/api/v1/tenants/current/users").json()
    assert not {m["id"] for m in members_a} & {m["id"] for m in members_b}
    assert all(m["full_name"] != "Collab A" for m in members_b)
    assert b.get("/api/v1/tenants/current").json()["name"] == "Studio B"

    target = next(m["id"] for m in members_a if m["full_name"] == "Collab A")
    r = b.patch(f"/api/v1/tenants/current/users/{target}", json={"status": "disabled"})
    assert r.status_code == 404  # il collaboratore di A non esiste per B
    assert (
        next(m for m in a.get("/api/v1/tenants/current/users").json() if m["id"] == target)[
            "status"
        ]
        == "active"
    )


def test_last_owner_cannot_be_removed(client: TestClient) -> None:
    signup_verified(client)
    me_row = next(m for m in client.get("/api/v1/tenants/current/users").json() if m["is_me"])
    for body in ({"role": "secretary"}, {"status": "disabled"}):
        r = client.patch(f"/api/v1/tenants/current/users/{me_row['id']}", json=body)
        assert r.status_code == 409 and r.json()["error"]["code"] == "ultimo_titolare"


def test_disabled_member_loses_access(app: FastAPI) -> None:
    owner, member = new_client(app), new_client(app)
    signup_verified(owner, "Studio Uno")
    email = unique_email("collab")
    owner.post(
        "/api/v1/tenants/current/users",
        json={"email": email, "full_name": "Luca Neri", "role": "professional"},
    )
    member.post(
        "/api/v1/auth/invitation/accept",
        json={"token": last_token("/invito"), "password": "Collaboratore-ok-5"},
    )
    assert member.get("/api/v1/auth/me").status_code == 200

    target = next(
        m["id"] for m in owner.get("/api/v1/tenants/current/users").json() if m["email"] == email
    )
    assert (
        owner.patch(
            f"/api/v1/tenants/current/users/{target}", json={"status": "disabled"}
        ).status_code
        == 204
    )
    assert member.get("/api/v1/auth/me").status_code == 401
    r = login(member, email, "Collaboratore-ok-5")
    assert r.status_code == 403 and r.json()["error"]["code"] == "nessuno_studio"


# ---------------------------------------------------------------- dati dello studio e registro


def test_update_studio_and_audit(client: TestClient, owner_engine: Engine) -> None:
    _, me = signup_verified(client)
    r = client.put(
        "/api/v1/tenants/current",
        json={
            "name": "Studio Rinnovato",
            "contact_phone": "+39 02 1234567",
            "cancellation_min_hours": 48,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Studio Rinnovato" and data["cancellation_min_hours"] == 48
    assert (
        client.put("/api/v1/tenants/current", json={"contact_phone": "chiamami"}).status_code == 422
    )
    assert (
        client.put("/api/v1/tenants/current", json={"cancellation_min_hours": 500}).status_code
        == 422
    )

    tenant_id = me["tenant"]["id"].replace("-", "")  # type: ignore[index]
    actions = {
        r[0]
        for r in sql(
            owner_engine, "SELECT action FROM audit_logs WHERE tenant_id = :t", t=tenant_id
        )
    }
    assert {"signup", "studio_updated"} <= actions


def test_failed_login_is_audited(client: TestClient, owner_engine: Engine) -> None:
    before = sql(owner_engine, "SELECT COUNT(*) FROM audit_logs WHERE action = 'login_failed'")[0][
        0
    ]
    login(client, unique_email(), "Password-sbagliata-1")
    after = sql(owner_engine, "SELECT COUNT(*) FROM audit_logs WHERE action = 'login_failed'")[0][0]
    assert after == before + 1  # type: ignore[operator]


def test_meta_endpoints(client: TestClient) -> None:
    assert client.get("/api/v1/meta/config").json() == {"signup_open": True}
    types = client.get("/api/v1/meta/business-types").json()
    assert len(types) == 14 and types[0] == {"code": "fisioterapista", "label": "Fisioterapista"}


def test_platform_session_requires_reason(app: FastAPI) -> None:
    with pytest.raises(ValueError), app.state.db.platform_session("  "):
        pass


def test_reset_password_window(client: TestClient, owner_engine: Engine) -> None:
    email, _ = signup_verified(client)
    client.post("/api/v1/auth/password/forgot", json={"email": email})
    token = last_token("/reimposta-password")
    sql(
        owner_engine,
        "UPDATE user_tokens SET expires_at = :t "
        "WHERE purpose = 'reset_password' AND used_at IS NULL",
        t="2000-01-01",
    )
    r = client.post(
        "/api/v1/auth/password/reset", json={"token": token, "password": "Nuova-password-sicura-9"}
    )
    assert r.status_code == 422
