"""Testi delle email (italiano). Nessun dato sanitario: solo dati amministrativi dell'account."""

from __future__ import annotations

from html import escape

from app.modules.email.sender import OutgoingEmail

FOOTER = "CoreNexus Agenda · email automatica, non rispondere a questo messaggio."


def _html(title: str, lines: list[str], button: tuple[str, str] | None, after: list[str]) -> str:
    body = "".join(f"<p style='margin:0 0 14px'>{escape(line)}</p>" for line in lines)
    if button:
        label, url = button
        body += (
            "<p style='margin:24px 0'><a href='" + escape(url, quote=True) + "' style='"
            "background:#0071e3;color:#fff;text-decoration:none;padding:12px 22px;"
            "border-radius:999px;font-weight:600;display:inline-block'>"
            + escape(label)
            + "</a></p>"
        )
    body += "".join(
        f"<p style='margin:0 0 10px;color:#86868b;font-size:13px'>{escape(line)}</p>"
        for line in after
    )
    return (
        "<!doctype html><html lang='it'><body style='margin:0;background:#f5f5f7;"
        "font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#1d1d1f'>"
        "<div style='max-width:520px;margin:0 auto;padding:32px 20px'>"
        "<div style='background:#fff;border-radius:16px;padding:28px'>"
        f"<h1 style='font-size:22px;margin:0 0 16px'>{escape(title)}</h1>{body}</div>"
        f"<p style='color:#86868b;font-size:12px;text-align:center;margin-top:16px'>{FOOTER}</p>"
        "</div></body></html>"
    )


def _mail(
    to: str,
    subject: str,
    title: str,
    lines: list[str],
    button: tuple[str, str] | None = None,
    after: list[str] | None = None,
) -> OutgoingEmail:
    after = after or []
    text = "\n\n".join(
        [title, *lines, *([f"{button[0]}: {button[1]}"] if button else []), *after, FOOTER]
    )
    return OutgoingEmail(to=to, subject=subject, text=text, html=_html(title, lines, button, after))


def verify_email(to: str, name: str, studio: str, url: str) -> OutgoingEmail:
    return _mail(
        to,
        "Conferma il tuo indirizzo email",
        f"Benvenuto, {name}",
        [
            f"Hai registrato lo studio «{studio}» su CoreNexus Agenda.",
            "Per attivare l'account conferma il tuo indirizzo email.",
        ],
        ("Conferma email", url),
        ["Il link scade tra 48 ore. Se non sei stato tu, ignora questo messaggio."],
    )


def already_registered(to: str, login_url: str, reset_url: str) -> OutgoingEmail:
    return _mail(
        to,
        "Hai già un account",
        "Hai già un account",
        [
            "Qualcuno ha provato a registrare uno studio con questo indirizzo email, "
            "ma esiste già un account associato.",
            "Puoi accedere oppure reimpostare la password.",
        ],
        ("Accedi", login_url),
        [f"Password dimenticata? {reset_url}", "Se non sei stato tu, ignora questo messaggio."],
    )


def reset_password(to: str, url: str) -> OutgoingEmail:
    return _mail(
        to,
        "Reimposta la password",
        "Reimposta la password",
        ["Abbiamo ricevuto una richiesta di reimpostazione della password del tuo account."],
        ("Scegli una nuova password", url),
        [
            "Il link scade tra 1 ora e si può usare una sola volta.",
            "Se non sei stato tu, ignora questo messaggio: la password resta quella attuale.",
        ],
    )


def invitation(to: str, inviter: str, studio: str, role: str, url: str) -> OutgoingEmail:
    return _mail(
        to,
        f"Invito a «{studio}» su CoreNexus Agenda",
        "Sei stato invitato",
        [
            f"{inviter} ti ha invitato nello studio «{studio}» con il ruolo {role}.",
            "Per accettare scegli la tua password.",
        ],
        ("Accetta l'invito", url),
        ["L'invito scade tra 7 giorni."],
    )


def added_to_studio(to: str, inviter: str, studio: str, role: str, login_url: str) -> OutgoingEmail:
    return _mail(
        to,
        f"Ora fai parte di «{studio}»",
        "Nuovo studio nel tuo account",
        [
            f"{inviter} ti ha aggiunto allo studio «{studio}» con il ruolo {role}.",
            "Accedi con le tue credenziali abituali e scegli lo studio dal tuo profilo.",
        ],
        ("Accedi", login_url),
    )


def client_login(to: str, url: str, studios: list[str]) -> OutgoingEmail:
    where = ", ".join(studios[:3]) + (" e altri" if len(studios) > 3 else "")
    return _mail(
        to,
        "Il tuo link per l'area clienti",
        "Entra nell'area clienti",
        [
            f"Hai chiesto di vedere i tuoi appuntamenti presso {where}.",
            "Premi il pulsante per entrare: non serve nessuna password.",
        ],
        ("Entra nell'area clienti", url),
        [
            "Il link vale 15 minuti e si può usare una sola volta.",
            "Se non hai fatto tu la richiesta, ignora questa email.",
        ],
    )


def platform_invite(to: str, name: str, url: str, first: bool) -> OutgoingEmail:
    return _mail(
        to,
        "Accesso all'area piattaforma CoreNexus Agenda",
        f"Ciao {name}",
        [
            "Prima configurazione dell'area piattaforma: scegli la password e collega "
            "l'app di autenticazione."
            if first
            else "Sei stato invitato nell'area piattaforma di CoreNexus Agenda.",
            "Ti servirà un'app per i codici a 6 cifre (Google Authenticator, Microsoft "
            "Authenticator o simili).",
        ],
        ("Configura l'accesso", url),
        ["Il link vale 24 ore e si può usare una sola volta."],
    )


def appointment_message(
    to: str,
    *,
    subject: str,
    title: str,
    lines: list[str],
    button: tuple[str, str] | None,
    after: list[str],
    studio: str,
    reply_to: str | None,
) -> OutgoingEmail:
    """Email al cliente su un appuntamento: mittente con il nome dello studio, risposte a lui."""
    mail = _mail(to, subject, title, lines, button, after)
    return OutgoingEmail(
        to=mail.to,
        subject=mail.subject,
        text=mail.text,
        html=mail.html,
        from_name=f"{studio} via Agenda",
        reply_to=reply_to,
    )
