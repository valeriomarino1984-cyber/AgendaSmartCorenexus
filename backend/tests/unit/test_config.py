import pytest
from pydantic import ValidationError

from app.core.config import Settings

BASE = {"database_url": "mysql+pymysql://u:p@h/db"}
PROD_OK = {
    **BASE,
    "environment": "production",
    "app_base_url": "https://agenda.corenexus.it",
    "public_booking_base_url": "https://agenda.corenexus.it/prenota",
    "cors_origins": ["https://agenda.corenexus.it"],
    "email_backend": "smtp",
    "smtp_host": "mail.corenexus.it",
}


def test_production_config_valid() -> None:
    assert Settings.model_validate(PROD_OK).is_production_like


@pytest.mark.parametrize(
    "override",
    [
        {"app_base_url": "http://agenda.corenexus.it"},
        {"public_booking_base_url": "http://agenda.corenexus.it/prenota"},
        {"cors_origins": ["*"]},
        {"log_json": False},
        {"email_backend": "file"},
        {"email_backend": "memory"},
        {"smtp_host": None},
    ],
)
def test_production_guards(override: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({**PROD_OK, **override})


def test_development_allows_http() -> None:
    s = Settings.model_validate({**BASE, "environment": "development"})
    assert s.app_base_url.startswith("http://")


@pytest.mark.parametrize("url", ["postgresql://u:p@h/db", "mysql://u:p@h/db", "sqlite:///x.db"])
def test_only_pymysql_urls(url: str) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({"database_url": url})


def test_secrets_not_in_repr() -> None:
    s = Settings.model_validate({"database_url": "mysql+pymysql://u:supersegreto@h/db"})
    assert "supersegreto" not in repr(s)


def test_secure_cookie_name_on_https() -> None:
    s = Settings.model_validate(PROD_OK)
    assert s.cookie_secure
    assert s.session_cookie_name == "__Host-agenda_session"
    dev = Settings.model_validate({**BASE, "environment": "development"})
    assert not dev.cookie_secure
    assert dev.session_cookie_name == "agenda_session"
