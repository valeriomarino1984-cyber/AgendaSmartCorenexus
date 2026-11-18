"""Codici a 6 cifre: valori di prova ufficiali (RFC 6238) e regole d'uso."""

from __future__ import annotations

from app.modules.platform.totp import code_at, derive_secret, otpauth_uri, verify

RFC_SECRET = b"12345678901234567890"


def test_rfc6238_sha1_vectors() -> None:
    # Appendice B della RFC 6238 (8 cifre, SHA-1).
    for t, expected in [
        (59, "94287082"),
        (1111111109, "07081804"),
        (1234567890, "89005924"),
        (2000000000, "69279037"),
    ]:
        assert code_at(RFC_SECRET, t // 30, digits=8) == expected


def test_verify_window_and_no_reuse() -> None:
    now = 1_700_000_000.0
    step = int(now // 30)
    code = code_at(RFC_SECRET, step)
    assert verify(RFC_SECRET, code, now, None) == step
    assert verify(RFC_SECRET, code[:3] + " " + code[3:], now, None) == step  # spazi ammessi
    assert verify(RFC_SECRET, code, now + 30, None) == step  # un intervallo dopo: ancora valido
    assert verify(RFC_SECRET, code, now + 90, None) is None  # troppo tardi
    assert verify(RFC_SECRET, code, now, last_step=step) is None  # già usato
    assert verify(RFC_SECRET, "12345", now, None) is None
    assert verify(RFC_SECRET, "abcdef", now, None) is None


def test_secret_depends_on_server_key_and_salt() -> None:
    a = derive_secret(b"k" * 32, "sale-1")
    assert len(a) == 20
    assert a != derive_secret(b"k" * 32, "sale-2")
    assert a != derive_secret(b"x" * 32, "sale-1")
    uri = otpauth_uri(a, "anna@corenexus.it")
    assert uri.startswith("otpauth://totp/CoreNexus%20Agenda%3Aanna%40corenexus.it?secret=")
    assert "issuer=CoreNexus+Agenda" in uri
