from alembic import command
from alembic.script import ScriptDirectory

from tests.conftest import alembic_config


def test_single_head() -> None:
    heads = ScriptDirectory.from_config(alembic_config()).get_heads()
    assert len(heads) == 1, f"più head Alembic: {heads}"


def test_migrations_are_reversible() -> None:
    cfg = alembic_config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
