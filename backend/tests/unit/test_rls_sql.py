import pytest

from app.core.rls import disable_tenant_rls_sql, enable_tenant_rls_sql


def test_enable_sql_contains_force_and_policy() -> None:
    sql = " ".join(enable_tenant_rls_sql("clients"))
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "current_tenant_id()" in sql
    assert "WITH CHECK" in sql


@pytest.mark.parametrize("name", ["clients; DROP TABLE x", "Clients", "a b", "", "x" * 64])
def test_identifier_injection_rejected(name: str) -> None:
    with pytest.raises(ValueError):
        enable_tenant_rls_sql(name)
    with pytest.raises(ValueError):
        disable_tenant_rls_sql(name)
