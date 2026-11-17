import pytest

from app.core.db import forbidden_privileges

USER = "TO `agenda_app`@`localhost`"


@pytest.mark.parametrize(
    "grants",
    [
        [f"GRANT USAGE ON *.* {USER}"],
        [
            f"GRANT USAGE ON *.* {USER}",
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON `agenda`.* {USER}",
        ],
    ],
)
def test_dml_only_is_accepted(grants: list[str]) -> None:
    assert forbidden_privileges(grants) == set()


@pytest.mark.parametrize(
    ("grant", "expected"),
    [
        (f"GRANT ALL PRIVILEGES ON `agenda`.* {USER}", {"ALL PRIVILEGES"}),
        (f"GRANT SELECT, CREATE, DROP ON `agenda`.* {USER}", {"CREATE", "DROP"}),
        (f"GRANT SELECT, ALTER, INDEX ON `agenda`.* {USER}", {"ALTER", "INDEX"}),
        (f"GRANT SELECT ON `agenda`.* {USER} WITH GRANT OPTION", {"GRANT OPTION"}),
    ],
)
def test_ddl_privileges_are_detected(grant: str, expected: set[str]) -> None:
    assert forbidden_privileges([grant]) == expected
