"""Configurazione applicativa: tutti i valori, segreti inclusi, arrivano da variabili d'ambiente."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "staging", "production"]

_PG_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Environment = "development"
    log_level: str = "INFO"
    log_json: bool = True

    # Ruolo applicativo: NON proprietario delle tabelle, senza BYPASSRLS.
    database_url: SecretStr
    # Ruolo proprietario dello schema: usato solo da Alembic, mai dall'applicazione.
    migrations_database_url: SecretStr | None = None
    # Nome del ruolo applicativo atteso: l'app rifiuta di avviarsi con un ruolo diverso.
    app_db_role: str = "corenexus_app"
    db_pool_size: int = Field(default=5, ge=1)
    db_max_overflow: int = Field(default=10, ge=0)

    redis_url: SecretStr = SecretStr("redis://localhost:6379/0")

    app_base_url: str = "http://localhost:3000"
    public_booking_base_url: str = "http://localhost:3000/prenota"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    sentry_dsn: SecretStr | None = None
    sentry_traces_sample_rate: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("app_db_role")
    @classmethod
    def _valid_role(cls, value: str) -> str:
        if not _PG_IDENTIFIER.match(value):
            raise ValueError("app_db_role non è un identificatore PostgreSQL valido")
        return value

    @property
    def is_production_like(self) -> bool:
        return self.environment in ("staging", "production")

    @model_validator(mode="after")
    def _production_guards(self) -> Settings:
        if not self.is_production_like:
            return self
        for name in ("app_base_url", "public_booking_base_url"):
            if not getattr(self, name).startswith("https://"):
                raise ValueError(f"{name} deve usare https in ambiente {self.environment}")
        if "*" in self.cors_origins:
            raise ValueError("cors_origins non può contenere '*' in ambiente " + self.environment)
        if not self.log_json:
            raise ValueError("log_json deve essere attivo in ambiente " + self.environment)
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # i valori obbligatori sono letti dall'ambiente
