"""Contrôles statiques du registre QR 033 proposé (jamais déployé)."""
from pathlib import Path

SQL = Path("sql/033_document_trace_registry_PREPARATION.sql").read_text(
    encoding="utf-8").lower()


def test_registre_prive_sans_exposition_api():
    for table in ("erp_document_trace", "erp_document_trace_version",
                  "erp_document_trace_event"):
        assert f"create table erp_private.{table} (" in SQL
        assert f"alter table erp_private.{table} enable row level security" in SQL
        assert f"alter table erp_private.{table} force row level security" in SQL
        assert f"revoke all on erp_private.{table}" in SQL
    assert "create policy" not in SQL
    assert "grant select" not in SQL and "grant execute" not in SQL
    assert "security definer" not in SQL


def test_registre_versions_et_evenements_coherents():
    assert "primary key (trace_id, version_no)" in SQL
    assert "foreign key (trace_id, version_no)" in SQL
    assert "references erp_private.erp_document_trace_version(trace_id, version_no)" in SQL
    assert "references erp_private.erp_document_trace(trace_id)" in SQL
    assert "references public.users(user_id)" in SQL
    assert "payload_sha256" in SQL
    assert "current_version" in SQL
    assert "actor_id" in SQL
    assert "on delete restrict" in SQL


def test_versions_et_evenements_immuables():
    assert "before update or delete on erp_private.erp_document_trace_version" in SQL
    assert "before update or delete on erp_private.erp_document_trace_event" in SQL
    assert "erp_document_trace_immutable()" in SQL
    assert "raise exception 'historique documentaire immuable'" in SQL
    assert "security invoker" in SQL
