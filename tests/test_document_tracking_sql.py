"""Vérifications statiques du projet SQL 033 non déployé."""
from pathlib import Path

SQL = Path("sql/033_document_trace_registry_PREPARATION.sql").read_text(encoding="utf-8").lower()


def test_registre_prive_sans_exposition_api():
    assert "create table erp_private.erp_document_trace (" in SQL
    assert "create table erp_private.erp_document_trace_event (" in SQL
    assert "enable row level security" in SQL
    assert "force row level security" in SQL
    assert "revoke all on erp_private.erp_document_trace from public" in SQL
    assert "revoke all on erp_private.erp_document_trace_event from public" in SQL
    assert "create policy" not in SQL
    assert "grant select" not in SQL and "grant execute" not in SQL
    assert "security definer" not in SQL


def test_registre_identifiant_et_integrite():
    assert "primary key" in SQL
    assert "payload_sha256" in SQL
    assert "references erp_private.erp_document_trace(trace_id)" in SQL
    assert "on delete restrict" in SQL
    assert "created_by" in SQL
    assert "actor_id" in SQL
    assert "document_type" in SQL
    assert "version_no" in SQL
