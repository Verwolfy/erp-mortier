"""Contrat SQL de l'audit SECURITY-01 : une seule requête SELECT, sans mutation."""
from pathlib import Path

import pytest

pglast = pytest.importorskip("pglast")

SQL = (
    Path(__file__).resolve().parents[1]
    / "sql/audits/security_public_surface_readonly_20261109.sql"
)


def test_audit_security_01_est_une_seule_requete_select():
    source = SQL.read_text(encoding="utf-8")
    parsed = pglast.parse_sql(source)
    assert len(parsed) == 1, "Audit multi-instructions interdit"
    assert type(parsed[0].stmt).__name__ == "SelectStmt"
    assert parsed[0].stmt.withClause is not None
    assert "FOR UPDATE" not in source.upper()
    assert "FOR SHARE" not in source.upper()


@pytest.mark.parametrize("expression", [
    "has_table_privilege('anon'",
    "has_table_privilege('authenticated'",
    "has_function_privilege('anon'",
    "has_function_privilege('authenticated'",
    "c.relrowsecurity", "c.reloptions", "p.prosecdef", "p.proconfig",
    "p.prorettype", "pg_catalog.trigger", "fonctions_clients_hors_trigger",
    "pol.polrelid = c.oid",
])
def test_audit_security_01_mesure_les_surfaces_attendues(expression):
    assert expression in SQL.read_text(encoding="utf-8")


def test_audit_security_01_ne_contient_aucune_fonction_volontairement_mutante():
    source = SQL.read_text(encoding="utf-8").lower()
    for forbidden in ("nextval(", "setval(", "pg_sleep(", "dblink(",
                      "pg_notify(", "pg_advisory_lock(", "lo_import("):
        assert forbidden not in source
