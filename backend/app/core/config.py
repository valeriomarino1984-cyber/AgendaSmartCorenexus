"""Configurazione applicativa: tutti i valori, segreti inclusi, arrivano da variabili d'ambiente."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "staging", "production"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Environment = "development"
    log_level: str = "INFO"
    log_json: bool = True

    # Utente applicativo MySQL/MariaDB: solo SELECT, INSERT, UPDATE, DELETE (nessun DDL).
    database_url: SecretStr
    # Utente con tutti i privilegi sul database: usato solo per le migrazioni Alembic.
    migrations_database_url: SecretStr | None = None
    db_pool_size: int = Field(default=5, ge=1)
    db_max_overflow: int = Field(default=5, ge=0)
    # Secondi dopo cui una connessione viene ricreata (MySQL chiude quelle inattive).
    db_pool_recycle: int = Field(default=280, ge=30)

    app_base_url: str = "http://localhost:3000"
    public_booking_base_url: str = "http://localhost:3000/prenota"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # Registrazione autonoma degli studi (come REGISTRAZIONE_APERTA in Presenze).
    signup_open: bool = False

    # Sessioni: cookie HttpOnly con token opaco salvato (come hash) nel database.
    session_idle_hours: int = Field(default=12, ge=1, le=72)
    session_max_days: int = Field(default=14, ge=1, le=90)

    # Email transazionali. "smtp" in staging/produzione; "file" e "memory" solo per sviluppo e test.
    email_backend: Literal["smtp", "file", "memory"] = "file"
    email_from: str = "CoreNexus Agenda <no-reply@corenexus.it>"
    email_file_dir: str = "var/mail"
    smtp_host: str | None = None
    smtp_port: int = 465
    smtp_security: Literal["ssl", "starttls"] = "ssl"
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_timeout_seconds: int = Field(default=15, ge=1, le=60)

    sentry_dsn: SecretStr | None = None
    sentry_traces_sample_rate: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("database_url", "migrations_database_url")
    @classmethod
    def _mysql_only(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and not value.get_secret_value().startswith("mysql+pymysql://"):
            raise ValueError("l'URL del database deve iniziare con mysql+pymysql://")
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
        if self.email_backend != "smtp":
            raise ValueError("email_backend deve essere 'smtp' in ambiente " + self.environment)
        if not self.smtp_host:
            raise ValueError("smtp_host è obbligatorio in ambiente " + self.environment)
        return self

    @property
    def cookie_secure(self) -> bool:
        return self.app_base_url.startswith("https://")

    @property
    def session_cookie_name(self) -> str:
        # Il prefisso __Host- impone Secure, Path=/ e nessun Domain: il cookie resta su questo host.
        return "__Host-agenda_session" if self.cookie_secure else "agenda_session"

    @property
    def allowed_origins(self) -> set[str]:
        """Origini da cui si accettano richieste che modificano dati (protezione CSRF)."""
        return {self.app_base_url.rstrip("/"), *(o.rstrip("/") for o in self.cors_origins)}


@lru_cache
def get_settings() -> Settings:
    return Settings()  # i valori obbligatori sono letti dall'ambiente
