"""Invio email. In produzione SMTP (account email del cPanel o provider UE).

"file" e "memory" esistono solo per sviluppo e test: la configurazione di staging/produzione
li rifiuta all'avvio (vedi Settings), quindi non possono finire online per errore.
"""

from __future__ import annotations

import smtplib
import ssl
import time
import uuid
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

import structlog

from app.core.config import Settings

log = structlog.get_logger("email")


@dataclass(frozen=True)
class OutgoingEmail:
    to: str
    subject: str
    text: str
    html: str | None = None


# Casella in memoria per i test (email_backend="memory").
MEMORY_OUTBOX: list[OutgoingEmail] = []


def _build(settings: Settings, mail: OutgoingEmail) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = settings.email_from
    msg["To"] = mail.to
    msg["Subject"] = mail.subject
    msg["Date"] = formatdate(localtime=False)
    msg["Message-ID"] = make_msgid(domain=settings.email_from.rsplit("@", 1)[-1].strip(">"))
    msg.set_content(mail.text)
    if mail.html:
        msg.add_alternative(mail.html, subtype="html")
    return msg


def send_email(settings: Settings, mail: OutgoingEmail) -> bool:
    """Invia l'email e restituisce True se è partita. Gli errori sono registrati, mai mostrati."""
    started = time.perf_counter()
    try:
        if settings.email_backend == "memory":
            MEMORY_OUTBOX.append(mail)
        elif settings.email_backend == "file":
            folder = Path(settings.email_file_dir)
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}.eml"
            path.write_bytes(bytes(_build(settings, mail)))
        else:
            _send_smtp(settings, _build(settings, mail))
    except Exception as exc:
        # Il destinatario non va nei log (dato personale): basta l'oggetto e il tipo di errore.
        log.error("email_failed", subject=mail.subject, error_type=type(exc).__name__)
        return False
    log.info(
        "email_sent",
        subject=mail.subject,
        backend=settings.email_backend,
        duration_ms=round((time.perf_counter() - started) * 1000, 1),
    )
    return True


def _send_smtp(settings: Settings, msg: EmailMessage) -> None:
    if not settings.smtp_host:
        raise RuntimeError("SMTP_HOST non configurato")
    context = ssl.create_default_context()
    timeout = settings.smtp_timeout_seconds
    server: smtplib.SMTP
    if settings.smtp_security == "ssl":
        server = smtplib.SMTP_SSL(
            settings.smtp_host, settings.smtp_port, timeout=timeout, context=context
        )
    else:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=timeout)
        server.starttls(context=context)
    with server:
        if settings.smtp_username and settings.smtp_password:
            server.login(settings.smtp_username, settings.smtp_password.get_secret_value())
        server.send_message(msg)
