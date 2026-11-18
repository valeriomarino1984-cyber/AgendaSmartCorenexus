"""Sprint 2: sedi, professionisti, prestazioni, clienti, consensi, profili, ruoli e isolamento."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.integration.conftest import new_client
from tests.integration.test_accounts import (
    last_token,
    register,
    signup_verified,
    sql,
    unique_email,
)

API = "/api/v1"


def invite_and_join(owner: TestClient, role: str, name: str = "Marco Neri") -> TestClient:
    r = owner.post(
        f"{API}/tenants/current/users",
        json={"email": unique_email(role), "full_name": name, "role": role},
    )
    assert r.status_code == 201, r.text
    guest = new_client(owner.app)  # type: ignore[arg-type]
    r = guest.post(
        f"{API}/auth/invitation/accept",
        json={"token": last_token("/invito"), "password": "Collega-sicuro-12"},
    )
    assert r.status_code == 200, r.text
    return guest


def new_studio(
    app: FastAPI, name: str = "Studio Prova", btype: str = "nutrizionista"
) -> TestClient:
    c = new_client(app)
    email = unique_email()
    register(c, email, name, business_type=btype)
    r = c.post(f"{API}/auth/verify-email", json={"token": last_token("/verifica-email")})
    assert r.status_code == 200, r.text
    return c


# ---------------------------------------------------------------- registrazione e profili


def test_signup_creates_location_owner_professional_and_profile(app: FastAPI) -> None:
    c = new_studio(app, "Studio Fisio", "fisioterapista")
    locations = c.get(f"{API}/locations").json()
    assert [(loc["name"], loc["is_default"]) for loc in locations] == [("Sede principale", True)]

    profs = c.get(f"{API}/professionals").json()
    assert len(profs) == 1 and profs[0]["name"] == "Anna Bianchi" and profs[0]["user_id"]

    services = c.get(f"{API}/services").json()
    assert [(s["name"], s["duration_minutes"]) for s in services] == [
        ("Valutazione fisioterapica", 60),
        ("Seduta di fisioterapia", 45),
        ("Terapia manuale", 30),
    ]
    assert all(s["professional_ids"] == [profs[0]["id"]] for s in services)
    assert all(s["preparation_minutes"] == 10 for s in services)


def test_generic_profile_and_reload_is_idempotent(app: FastAPI) -> None:
    c = new_studio(app, "Centro Relax", "estetista")
    preview = c.get(f"{API}/services/profile").json()
    assert preview["profile"] == "generico"
    assert all(s["already_present"] for s in preview["services"])
    assert c.post(f"{API}/services/profile").json() == {"profile": "generico", "created": 0}

    first = c.get(f"{API}/services").json()[0]
    c.patch(f"{API}/services/{first['id']}", json={"name": "Primo incontro conoscitivo"})
    assert c.post(f"{API}/services/profile").json()["created"] == 1  # ricrea solo quello mancante
    assert len(c.get(f"{API}/services").json()) == 3


def test_profile_follows_category_change(app: FastAPI) -> None:
    c = new_studio(app, "Studio Mente", "estetista")
    c.put(f"{API}/tenants/current", json={"business_type": "psicoterapeuta"})
    preview = c.get(f"{API}/services/profile").json()
    assert preview["profile"] == "psicologo"
    assert c.post(f"{API}/services/profile").json()["created"] == 3
    online = [s for s in c.get(f"{API}/services").json() if s["mode"] == "online"]
    assert [s["name"] for s in online] == ["Colloquio online"]


def test_invited_professional_gets_a_card_secretary_does_not(app: FastAPI) -> None:
    owner = new_studio(app)
    invite_and_join(owner, "professional", "Luca Moretti")
    invite_and_join(owner, "secretary", "Sara Galli")
    names = {p["name"] for p in owner.get(f"{API}/professionals").json()}
    assert names == {"Anna Bianchi", "Luca Moretti"}

    members = owner.get(f"{API}/tenants/current/users").json()
    sara = next(m for m in members if m["full_name"] == "Sara Galli")
    owner.patch(f"{API}/tenants/current/users/{sara['id']}", json={"role": "professional"})
    names = {p["name"] for p in owner.get(f"{API}/professionals").json()}
    assert "Sara Galli" in names


# ---------------------------------------------------------------- sedi e professionisti


def test_update_location_rules(app: FastAPI) -> None:
    c = new_studio(app)
    loc = c.get(f"{API}/locations").json()[0]
    r = c.patch(
        f"{API}/locations/{loc['id']}",
        json={
            "name": "Studio Via Roma",
            "address": "Via Roma 1, Milano",
            "timezone": "Europe/Rome",
        },
    )
    assert r.status_code == 200 and r.json()["address"] == "Via Roma 1, Milano"
    r = c.patch(f"{API}/locations/{loc['id']}", json={"active": False})
    assert r.status_code == 409 and r.json()["error"]["code"] == "sede_principale"
    r = c.patch(f"{API}/locations/{loc['id']}", json={"timezone": "Marte/Base"})
    assert r.status_code == 422


def test_professional_crud_and_validation(client: TestClient) -> None:
    signup_verified(client)
    r = client.post(
        f"{API}/professionals",
        json={"name": "Dott.ssa Elena Rossi", "specialization": "Dietista", "color": "#FF9500"},
    )
    assert r.status_code == 201, r.text
    prof = r.json()
    assert prof["color"] == "#ff9500" and prof["user_id"] is None and prof["status"] == "active"

    r = client.patch(f"{API}/professionals/{prof['id']}", json={"status": "inactive"})
    assert r.status_code == 200 and r.json()["status"] == "inactive"
    assert (
        client.post(f"{API}/professionals", json={"name": "X", "color": "rosso"}).status_code == 422
    )

    me = client.get(f"{API}/auth/me").json()
    r = client.post(f"{API}/professionals", json={"name": "Doppione", "user_id": me["user"]["id"]})
    assert r.status_code == 409 and r.json()["error"]["code"] == "professionista_esistente"


def test_cannot_link_account_of_other_studio(app: FastAPI) -> None:
    a, b = new_studio(app, "Studio A"), new_studio(app, "Studio B")
    user_b = b.get(f"{API}/auth/me").json()["user"]["id"]
    r = a.post(f"{API}/professionals", json={"name": "Intruso", "user_id": user_b})
    assert r.status_code == 422 and r.json()["error"]["code"] == "account_non_valido"


# ---------------------------------------------------------------- prestazioni


def test_service_crud_modes_and_professionals(client: TestClient) -> None:
    signup_verified(client)
    owner_prof = client.get(f"{API}/professionals").json()[0]["id"]
    other = client.post(f"{API}/professionals", json={"name": "Elena Rossi"}).json()["id"]

    r = client.post(
        f"{API}/services",
        json={
            "name": "Consulenza online",
            "duration_minutes": 40,
            "price": "55.50",
            "mode": "online",
            "professional_ids": [other],
        },
    )
    assert r.status_code == 201, r.text
    svc = r.json()
    assert (
        svc["price"] == "55.50" and svc["mode"] == "online" and svc["professional_ids"] == [other]
    )

    r = client.patch(
        f"{API}/services/{svc['id']}",
        json={"mode": "both", "professional_ids": [owner_prof, other], "active": False},
    )
    assert r.status_code == 200
    assert r.json()["mode"] == "both" and sorted(r.json()["professional_ids"]) == sorted(
        [owner_prof, other]
    )
    assert r.json()["active"] is False

    # Senza elenco: abilitati tutti i professionisti attivi.
    r = client.post(f"{API}/services", json={"name": "Visita", "duration_minutes": 30})
    assert sorted(r.json()["professional_ids"]) == sorted([owner_prof, other])

    for bad in [
        {"name": "Troppo breve", "duration_minutes": 2},
        {"name": "Prezzo", "duration_minutes": 30, "price": "-1"},
        {"name": "Modo", "duration_minutes": 30, "mode": "telefono"},
        {"name": "Prep", "duration_minutes": 30, "preparation_minutes": 500},
    ]:
        assert client.post(f"{API}/services", json=bad).status_code == 422, bad


def test_service_rejects_professional_of_other_studio(app: FastAPI) -> None:
    a, b = new_studio(app, "Studio A"), new_studio(app, "Studio B")
    prof_b = b.get(f"{API}/professionals").json()[0]["id"]
    r = a.post(
        f"{API}/services",
        json={"name": "Mista", "duration_minutes": 30, "professional_ids": [prof_b]},
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "professionista_non_valido"


# ---------------------------------------------------------------- clienti


def test_client_create_search_update_archive(client: TestClient, owner_engine: Engine) -> None:
    signup_verified(client)
    r = client.post(
        f"{API}/clients",
        json={
            "first_name": " Giulia ",
            "last_name": "Ferri",
            "phone": "333 123 4567",
            "email": "Giulia.Ferri@Example.com",
            "birth_date": "1990-05-12",
            "admin_notes": "Preferisce il mattino",
            "email_consent": True,
        },
    )
    assert r.status_code == 201, r.text
    giulia = r.json()
    assert giulia["first_name"] == "Giulia" and giulia["phone"] == "+393331234567"
    assert giulia["email"] == "giulia.ferri@example.com"
    assert giulia["email_consent"] is True and giulia["email_consent_at"]
    assert giulia["whatsapp_consent"] is False and giulia["marketing_consent"] is False

    client.post(f"{API}/clients", json={"first_name": "Marco", "last_name": "Conti"})
    for q, expected in [
        ("ferri", {"Giulia"}),
        ("1234", {"Giulia"}),
        ("mar con", {"Marco"}),
        ("100%", set()),
        ("", {"Giulia", "Marco"}),
    ]:
        items = client.get(f"{API}/clients", params={"q": q}).json()["items"]
        assert {c["first_name"] for c in items} == expected, q

    r = client.patch(f"{API}/clients/{giulia['id']}", json={"phone": "abc"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "telefono_non_valido"
    r = client.patch(f"{API}/clients/{giulia['id']}", json={"phone": None, "admin_notes": ""})
    assert r.json()["phone"] is None and r.json()["admin_notes"] is None

    assert client.delete(f"{API}/clients/{giulia['id']}").status_code == 204
    active = client.get(f"{API}/clients").json()
    assert active["total"] == 1
    archived = client.get(f"{API}/clients", params={"status": "archived"}).json()["items"]
    assert [c["first_name"] for c in archived] == ["Giulia"]
    assert client.post(f"{API}/clients/{giulia['id']}/restore").status_code == 204
    assert client.get(f"{API}/clients").json()["total"] == 2

    # Il registro attività non contiene i dati del cliente, solo i nomi dei campi.
    rows = sql(
        owner_engine,
        "SELECT details FROM audit_logs WHERE resource_id = :id AND action = 'client_updated'",
        id=giulia["id"],
    )
    assert rows and all("Preferisce" not in str(r[0]) for r in rows)


def test_duplicate_client_warning_and_force(client: TestClient) -> None:
    signup_verified(client)
    body = {"first_name": "Luca", "last_name": "Moretti", "phone": "+39 340 000 1111"}
    assert client.post(f"{API}/clients", json=body).status_code == 201
    r = client.post(f"{API}/clients", json={**body, "first_name": "Luca Maria"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "cliente_duplicato"
    assert r.json()["error"]["details"]["existing_id"]
    assert client.post(f"{API}/clients", params={"force": "true"}, json=body).status_code == 201


def test_consent_changes_are_recorded(client: TestClient) -> None:
    signup_verified(client)
    c = client.post(
        f"{API}/clients",
        json={
            "first_name": "Sara",
            "last_name": "Galli",
            "whatsapp_consent": True,
            "marketing_consent": False,  # un "no" iniziale non è una revoca: nessun evento
        },
    ).json()
    client.patch(f"{API}/clients/{c['id']}", json={"whatsapp_consent": True})  # nessun cambio
    client.patch(
        f"{API}/clients/{c['id']}", json={"whatsapp_consent": False, "marketing_consent": True}
    )
    detail = client.get(f"{API}/clients/{c['id']}").json()
    history = sorted((e["channel"], e["action"]) for e in detail["consent_history"])
    assert history == [
        ("marketing", "granted"),
        ("whatsapp", "granted"),
        ("whatsapp", "revoked"),
    ]
    assert all(e["source"] == "staff" for e in detail["consent_history"])
    assert detail["whatsapp_consent"] is False and detail["marketing_consent"] is True


def test_client_validation(client: TestClient) -> None:
    signup_verified(client)
    for bad in [
        {"first_name": "", "last_name": "X"},
        {"first_name": "   ", "last_name": "X"},
        {"first_name": "A", "last_name": "B", "email": "non-una-email"},
        {"first_name": "A", "last_name": "B", "birth_date": "2999-01-01"},
        {"first_name": "A", "last_name": "B", "preferred_channel": "sms"},
    ]:
        assert client.post(f"{API}/clients", json=bad).status_code == 422, bad


# ---------------------------------------------------------------- ruoli


def test_roles_on_catalog(app: FastAPI) -> None:
    owner = new_studio(app)
    secretary = invite_and_join(owner, "secretary", "Sara Galli")
    professional = invite_and_join(owner, "professional", "Luca Moretti")
    svc = owner.get(f"{API}/services").json()[0]["id"]
    prof = owner.get(f"{API}/professionals").json()[0]["id"]
    loc = owner.get(f"{API}/locations").json()[0]["id"]

    for staff in (secretary, professional):
        for path in ("/services", "/professionals", "/locations", "/clients"):
            assert staff.get(f"{API}{path}").status_code == 200, path
        for method, path, body in [
            ("post", "/services", {"name": "X", "duration_minutes": 30}),
            ("patch", f"/services/{svc}", {"name": "X"}),
            ("post", "/services/profile", None),
            ("post", "/professionals", {"name": "X"}),
            ("patch", f"/professionals/{prof}", {"name": "X"}),
            ("patch", f"/locations/{loc}", {"name": "X"}),
        ]:
            call = getattr(staff, method)
            r = call(f"{API}{path}", json=body) if body else call(f"{API}{path}")
            assert r.status_code == 403, (method, path)
        # I clienti li gestisce tutto lo staff.
        r = staff.post(f"{API}/clients", json={"first_name": "Nuovo", "last_name": unique_email()})
        assert r.status_code == 201

    guest = new_client(app)
    assert guest.get(f"{API}/clients").status_code == 401


# ---------------------------------------------------------------- isolamento


def test_catalog_isolation_between_studios(app: FastAPI) -> None:
    a, b = new_studio(app, "Studio A"), new_studio(app, "Studio B")
    client_a = a.post(f"{API}/clients", json={"first_name": "Solo", "last_name": "DiA"}).json()
    svc_a = a.get(f"{API}/services").json()[0]["id"]
    prof_a = a.get(f"{API}/professionals").json()[0]["id"]
    loc_a = a.get(f"{API}/locations").json()[0]["id"]

    assert b.get(f"{API}/clients", params={"q": "Solo"}).json()["total"] == 0
    assert all(s["id"] != svc_a for s in b.get(f"{API}/services").json())
    assert all(p["id"] != prof_a for p in b.get(f"{API}/professionals").json())
    assert all(loc["id"] != loc_a for loc in b.get(f"{API}/locations").json())

    for method, path, body in [
        ("get", f"/clients/{client_a['id']}", None),
        ("patch", f"/clients/{client_a['id']}", {"first_name": "Rubato"}),
        ("delete", f"/clients/{client_a['id']}", None),
        ("post", f"/clients/{client_a['id']}/restore", None),
        ("patch", f"/services/{svc_a}", {"name": "Rubato"}),
        ("patch", f"/professionals/{prof_a}", {"name": "Rubato"}),
        ("patch", f"/locations/{loc_a}", {"name": "Rubato"}),
    ]:
        call = getattr(b, method)
        r = call(f"{API}{path}", json=body) if body else call(f"{API}{path}")
        assert r.status_code == 404, (method, path)

    # B non può indicare un professionista di A come riferimento di un proprio cliente.
    r = b.post(
        f"{API}/clients",
        json={"first_name": "X", "last_name": "Y", "reference_professional_id": prof_a},
    )
    assert r.status_code == 422

    assert a.get(f"{API}/clients/{client_a['id']}").json()["first_name"] == "Solo"
    assert a.get(f"{API}/clients/{client_a['id']}").json()["status"] == "active"
