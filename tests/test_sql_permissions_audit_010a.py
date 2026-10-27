"""010-A-02 — audit statique, sans connexion à la base ni réseau."""

from pathlib import Path
import re

from scripts.verifier_audit_permissions_010a import (
    EXPECTED_RPC, EXPECTED_TECH_TABLES,
)

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "sql" / "010A_02_permissions_audit_readonly.sql"


def _without_sql_comments(sql: str) -> str:
    return "\n".join(line.split("--", 1)[0] for line in sql.splitlines())


def test_sql_audit_is_a_single_read_only_query():
    sql = _without_sql_comments(AUDIT.read_text(encoding="utf-8"))
    assert re.search(r"\bWITH\b", sql, re.I)
    assert re.search(r"\bSELECT\s+categorie\b", sql, re.I)
    for forbidden in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "GRANT", "REVOKE", "EXECUTE", "CALL", "DO", "MERGE", "COPY", "BEGIN", "COMMIT", "ROLLBACK"):
        # Only standalone statements are prohibited. Words inside strings/columns
        # like 'execute_anon' are deliberately not matched.
        assert not re.search(rf"^\s*{forbidden}\b", sql, re.I | re.M), forbidden
    assert sql.strip().endswith(";")


def test_expected_functions_are_present_in_audit():
    sql = AUDIT.read_text(encoding="utf-8")
    for name in EXPECTED_RPC:
        assert f"'{name}'" in sql
    assert "has_function_privilege" in sql
    assert "to_regprocedure" in sql
    assert "prosecdef" in sql
    assert "SURCHARGE_RPC" in sql


def test_expected_technical_tables_are_present_in_audit():
    sql = AUDIT.read_text(encoding="utf-8")
    for name in EXPECTED_TECH_TABLES:
        assert f"('{name}')" in sql or f"('{name}')," in sql
    assert "relrowsecurity" in sql
    assert "pg_policy" in sql
    assert "has_table_privilege" in sql


def test_expected_rpc_signatures_match_migration_files():
    # Prevent a misleading 'missing RPC' if the callable function's signature
    # changed in a SQL migration and the auditor was not updated.
    audit_sql = AUDIT.read_text(encoding="utf-8")
    for migration in sorted((ROOT / "sql").glob("00[2-9]_*.sql")):
        content = migration.read_text(encoding="utf-8-sig")
        for match in re.finditer(r"CREATE OR REPLACE FUNCTION public\.(\w+)\s*\(([^)]*)\)",
                                 content, flags=re.I | re.S):
            name, params = match.groups()
            types = [part.strip().split()[-1] for part in params.split(",") if part.strip()]
            sig = f"public.{name}({','.join(types)})"
            assert sig in audit_sql, f"Signature oubliée : {migration.name} -> {sig}"
