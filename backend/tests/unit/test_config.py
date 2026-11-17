import pytest
from pydantic import ValidationError

from app.core.config import Settings

BASE = {"database_url": "postgresql+asyncpg://u:p@h/db"}
PROD_OK = {
    **BASE,
    "environment": "production",
    "app_base_url": "https://agenda.corenexus.it",
    "public_booking_base_url": "https://agenda.corenexus.it/prenota",
    "cors_origins": ["https://agenda.corenexus.it"],
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
    ],
)
def test_production_guards(override: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({**PROD_OK, **override})


def test_development_allows_http() -> None:
    assert Settings.model_validate({**BASE, "environment": "development"}).app_base_url.startswith(
        "http://"
    )


@pytest.mark.parametrize("role", ["App", "app; DROP TABLE x", "1app", ""])
def test_invalid_db_role_rejected(role: str) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({**BASE, "app_db_role": role})


def test_secrets_not_in_repr() -> None:
    s = Settings(database_url="postgresql+asyncpg://u:supersegreto@h/db")
    assert "supersegreto" not in repr(s)
