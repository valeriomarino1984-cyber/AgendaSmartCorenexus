"""Backup cifrato e prova di ripristino (ops/backup-db.sh, ops/restore-db.sh) sul DB di test."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url

OPS = Path(__file__).resolve().parents[2] / "ops"
RESTORE_DB = "agenda_restore_test"

pytestmark = pytest.mark.skipif(
    not (shutil.which("mariadb-dump") or shutil.which("mysqldump")) or not shutil.which("openssl"),
    reason="servono mysqldump e openssl",
)


@pytest.fixture()
def env(tmp_path: Path) -> dict[str, str]:
    url = make_url(os.environ["MIGRATIONS_DATABASE_URL"])
    cnf = tmp_path / "backup.cnf"
    cnf.write_text(
        "[client]\n"
        f"user={url.username}\npassword={url.password}\n"
        f"host={url.host}\nport={url.port or 3306}\nprotocol=TCP\n"
        f"database={url.database}\n"
    )
    key = tmp_path / "backup.key"
    key.write_text("chiave-di-prova-lunga-almeno-32-caratteri!\n")
    for f in (cnf, key):
        f.chmod(0o600)
    return {
        **os.environ,
        "BACKUP_CNF": str(cnf),
        "BACKUP_PASSPHRASE_FILE": str(key),
        "BACKUP_DIR": str(tmp_path / "backup"),
        "BACKUP_KEEP_DAYS": "14",
    }


def run(script: str, env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    bash = shutil.which("bash") or "/bin/bash"
    return subprocess.run(  # noqa: S603 - script del repository, argomenti scelti dai test
        [bash, str(OPS / script), *args], env=env, capture_output=True, text=True, timeout=120
    )


def restore_engine() -> Engine:
    url = make_url(os.environ["MIGRATIONS_DATABASE_URL"]).set(database=RESTORE_DB)
    return create_engine(url)


def test_backup_is_encrypted_verified_and_restorable(
    env: dict[str, str], owner_engine: Engine
) -> None:
    r = run("backup-db.sh", env)
    assert r.returncode == 0, r.stderr
    files = sorted(Path(env["BACKUP_DIR"]).glob("agenda-*.sql.gz.enc"))
    assert len(files) == 1 and "Backup verificato" in r.stdout
    data = files[0].read_bytes()
    assert data.startswith(b"Salted__")  # cifrato: niente SQL leggibile
    assert b"CREATE TABLE" not in data and b"INSERT INTO" not in data
    assert Path(f"{files[0]}.sha256").exists()
    assert not list(Path(env["BACKUP_DIR"]).glob("*.part"))

    r = run("restore-db.sh", env, str(files[0]), RESTORE_DB)
    assert r.returncode == 0, r.stderr
    with owner_engine.connect() as live, restore_engine().connect() as copy:
        version = live.scalar(text("SELECT version_num FROM alembic_version"))
        assert copy.scalar(text("SELECT version_num FROM alembic_version")) == version
        assert f"Versione dello schema: {version}" in r.stdout
        for table in ("tenants", "users", "appointments"):
            q = text(f"SELECT COUNT(*) FROM {table}")
            assert copy.scalar(q) == live.scalar(q), table


def test_restore_refuses_production_and_bad_files(env: dict[str, str], tmp_path: Path) -> None:
    assert run("backup-db.sh", env).returncode == 0
    backup = next(Path(env["BACKUP_DIR"]).glob("agenda-*.sql.gz.enc"))
    live = make_url(os.environ["MIGRATIONS_DATABASE_URL"]).database or ""

    r = run("restore-db.sh", env, str(backup), live)
    assert r.returncode != 0 and "--forza" in r.stderr
    r = run("restore-db.sh", env, str(backup), "x; DROP DATABASE y")
    assert r.returncode != 0 and "non valido" in r.stderr

    # File alterato: la somma SHA-256 non torna e non si ripristina nulla.
    broken = tmp_path / "rotto.sql.gz.enc"
    raw = bytearray(backup.read_bytes())
    raw[-1] ^= 0xFF
    broken.write_bytes(bytes(raw))
    shutil.copy(f"{backup}.sha256", f"{broken}.sha256")
    Path(f"{broken}.sha256").write_text(
        Path(f"{broken}.sha256").read_text().replace(backup.name, broken.name)
    )
    r = run("restore-db.sh", env, str(broken), RESTORE_DB)
    assert r.returncode != 0 and "SHA-256" in r.stderr

    # Chiave sbagliata: la decifratura fallisce.
    wrong = tmp_path / "altra.key"
    wrong.write_text("un-altra-chiave-lunga-almeno-32-caratteri\n")
    wrong.chmod(0o600)
    r = run("restore-db.sh", {**env, "BACKUP_PASSPHRASE_FILE": str(wrong)}, str(backup), RESTORE_DB)
    assert r.returncode != 0


def test_backup_checks_setup_and_rotates(env: dict[str, str], tmp_path: Path) -> None:
    key = Path(env["BACKUP_PASSPHRASE_FILE"])
    key.chmod(0o644)
    r = run("backup-db.sh", env)
    assert r.returncode != 0 and "permessi 600" in r.stderr
    key.chmod(0o600)

    short = tmp_path / "corta.key"
    short.write_text("breve")
    short.chmod(0o600)
    r = run("backup-db.sh", {**env, "BACKUP_PASSPHRASE_FILE": str(short)})
    assert r.returncode != 0 and "troppo corta" in r.stderr

    # Credenziali sbagliate: errore, e nessun file parziale resta nella cartella.
    cnf = Path(env["BACKUP_CNF"])
    bad = tmp_path / "bad.cnf"
    bad.write_text(cnf.read_text().replace("password=", "password=sbagliata"))
    bad.chmod(0o600)
    r = run("backup-db.sh", {**env, "BACKUP_CNF": str(bad)})
    assert r.returncode != 0
    assert not list(Path(env["BACKUP_DIR"]).glob("*"))

    # Conservazione: i backup più vecchi di BACKUP_KEEP_DAYS vengono cancellati.
    folder = Path(env["BACKUP_DIR"])
    folder.mkdir(exist_ok=True)
    old = folder / "agenda-20200101-000000.sql.gz.enc"
    old.write_bytes(b"vecchio")
    past = time.time() - 30 * 86400
    os.utime(old, (past, past))
    assert run("backup-db.sh", env).returncode == 0
    assert not old.exists()
    assert len(list(folder.glob("agenda-*.sql.gz.enc"))) == 1
