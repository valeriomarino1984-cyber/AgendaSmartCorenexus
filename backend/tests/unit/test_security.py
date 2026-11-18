import pytest

from app.core.security import (
    hash_password,
    needs_rehash,
    password_problem,
    token_hash,
    verify_password,
)
from app.modules.accounts.service import _slugify


def test_hash_and_verify() -> None:
    stored = hash_password("Una-password-lunga-42")
    assert stored.startswith("scrypt$")
    assert "Una-password-lunga-42" not in stored
    assert verify_password("Una-password-lunga-42", stored)
    assert not verify_password("Una-password-lunga-43", stored)
    assert not needs_rehash(stored)


def test_same_password_gives_different_hashes() -> None:
    assert hash_password("Una-password-lunga-42") != hash_password("Una-password-lunga-42")


def test_verify_without_hash_is_false() -> None:
    assert not verify_password("qualsiasi-cosa-123", None)
    assert not verify_password("qualsiasi-cosa-123", "formato-sconosciuto")


def test_old_parameters_need_rehash() -> None:
    assert needs_rehash("scrypt$16384$8$1$c2FsdA$a2V5")
    assert needs_rehash("bcrypt$qualcosa")


@pytest.mark.parametrize(
    ("password", "fragment"),
    [
        ("corta1!", "almeno 10"),
        ("x" * 129, "al massimo"),
        ("mario.rossi-2026!", "email"),
        ("Benedetta2026!!", "nome"),
        ("aaaaaaaaaaaa", "semplice"),
    ],
)
def test_password_rules(password: str, fragment: str) -> None:
    problem = password_problem(
        password, email="mario.rossi@example.com", full_name="Benedetta Pucci"
    )
    assert problem is not None and fragment in problem


def test_good_password_accepted() -> None:
    assert password_problem("Tramonto-sul-lago-7", email="a@b.it", full_name="Anna Bianchi") is None


def test_token_hash_is_stable_and_not_reversible() -> None:
    assert token_hash("abc") == token_hash("abc")
    assert token_hash("abc") != "abc" and len(token_hash("abc")) == 64


@pytest.mark.parametrize(
    ("name", "slug"),
    [
        ("Studio Rossi", "studio-rossi"),
        ("Fisioterapia Città & Benessere", "fisioterapia-citta-benessere"),
        ("!!!", "studio"),
    ],
)
def test_slugify(name: str, slug: str) -> None:
    assert _slugify(name) == slug
