"""OPT-04 : mesures sans données privées ni contexte utilisateur persistant."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from core import db_service as db
from core import strict_reads as reads
from core.query_diagnostics import (
    measured_query_stage,
    query_metrics_scope,
    query_metrics_snapshot,
    record_cache_hit,
)
from modules.dashboards import service


def test_no_metrics_without_scope():
    assert query_metrics_snapshot() is None
    with measured_query_stage("select"):
        pass
    record_cache_hit()
    assert query_metrics_snapshot() is None


def test_snapshot_only_has_aggregates_and_cannot_mutate_live_stats():
    with query_metrics_scope():
        with measured_query_stage("check"):
            pass
        with measured_query_stage("select"):
            pass
        with measured_query_stage("client"):
            pass
        record_cache_hit()
        metrics = query_metrics_snapshot()
        assert metrics is not None
        assert metrics["checks"] == 1
        assert metrics["selects"] == 1
        assert metrics["clients"] == 1
        assert metrics["cache_hits"] == 1
        assert all(metrics[k] >= 0 for k in ("check_ms", "select_ms", "client_ms"))
        assert len(metrics) == 7
        assert all("password" not in k and "user" not in k for k in metrics)
        metrics["checks"] = 99999
        assert query_metrics_snapshot()["checks"] == 1
    assert query_metrics_snapshot() is None


def test_failing_stage_is_counted_without_its_error_or_payload():
    with query_metrics_scope():
        with pytest.raises(PermissionError, match="private-test-sentinel"):
            with measured_query_stage("check"):
                raise PermissionError("private-test-sentinel")
        metrics = query_metrics_snapshot()
        assert metrics["checks"] == 1
        assert "private-test-sentinel" not in str(metrics)


def test_nested_metrics_scope_restores_outer_state():
    with query_metrics_scope():
        record_cache_hit()
        with query_metrics_scope():
            with measured_query_stage("select"):
                pass
            assert query_metrics_snapshot()["selects"] == 1
            assert query_metrics_snapshot()["cache_hits"] == 0
        assert query_metrics_snapshot()["selects"] == 0
        assert query_metrics_snapshot()["cache_hits"] == 1
    assert query_metrics_snapshot() is None


@pytest.mark.parametrize("invalid", ["", "SELECT", "secret", "auth", "latency"])
def test_unrecognized_stage_refused_without_leak(invalid):
    with pytest.raises(ValueError):
        with measured_query_stage(invalid):
            pass


def test_strict_read_counts_pages_and_auth_without_changing_contract(monkeypatch):
    class Query:
        def select(self, projection, *, count):
            assert projection == "facture_id"
            assert count == "exact"
            return self

        def order(self, key):
            assert key == "facture_id"
            return self

        def range(self, start, end):
            assert (start, end) == (0, 499)
            return self

        def execute(self):
            return SimpleNamespace(data=[{"facture_id": "TEST-001"}], count=1)

    client = SimpleNamespace(table=lambda name: Query())
    checks = []
    monkeypatch.setattr(
        reads.db, "_require_read_permission",
        lambda table: checks.append(table),
    )
    monkeypatch.setattr(reads.db, "get_supabase_client", lambda: client)
    with query_metrics_scope():
        result = reads.fetch_data_strict("factures", only_primary_key=True)
        metrics = query_metrics_snapshot()
    assert result == [{"facture_id": "TEST-001"}]
    assert checks == ["factures"]
    assert metrics["checks"] == 1
    assert metrics["selects"] == 1
    assert metrics["clients"] == 0  # client de test substitué, pas de création


def test_strict_permission_denial_never_runs_select(monkeypatch):
    monkeypatch.setattr(
        reads.db, "_require_read_permission",
        lambda *_: (_ for _ in ()).throw(PermissionError("refus")),
    )
    monkeypatch.setattr(
        reads.db, "get_supabase_client",
        lambda: pytest.fail("Le droit refusé doit bloquer toute lecture"),
    )
    with query_metrics_scope():
        with pytest.raises(PermissionError):
            reads.fetch_data_strict("factures")
        metrics = query_metrics_snapshot()
    assert metrics["checks"] == 1
    assert metrics["selects"] == 0


def test_client_creation_is_measured_but_never_cached(monkeypatch):
    calls = []
    fake_secrets = {"supabase": {"url": "https://factice.invalid", "key": "only-test-value"}}
    monkeypatch.setattr(db.st, "secrets", fake_secrets)
    monkeypatch.setattr(db, "policy_from_streamlit", lambda _: object())
    monkeypatch.setattr(db, "require_supabase_target", lambda *_: None)

    def fake_create(url, key):
        calls.append((url, key))
        return SimpleNamespace(unique=len(calls))

    monkeypatch.setattr(db, "create_client", fake_create)
    with query_metrics_scope():
        a, b = db.get_supabase_client(), db.get_supabase_client()
        metrics = query_metrics_snapshot()
    assert (a.unique, b.unique) == (1, 2)
    assert len(calls) == 2
    assert metrics["clients"] == 2
    assert metrics["client_ms"] >= 0
    assert "only-test-value" not in str(metrics)


def test_dashboard_scope_caches_reads_and_restores_diagnostics(monkeypatch):
    calls = []
    monkeypatch.setattr(
        service, "fetch_data",
        lambda name: calls.append(name) or [{"facture_id": "DEMO-FAUX"}],
    )
    with service.dashboard_read_scope():
        assert service.charger_donnees("factures").iloc[0]["facture_id"] == "DEMO-FAUX"
        service.charger_donnees("factures")
        service.charger_donnees("factures")
        assert query_metrics_snapshot()["cache_hits"] == 2
    assert calls == ["factures"]
    assert query_metrics_snapshot() is None


def test_demo_data_never_creates_clients_or_selects(monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail("Le mode DEMO ne doit pas contacter Supabase")

    monkeypatch.setattr(service, "fetch_data", fail)
    monkeypatch.setattr(service, "fetch_data_by_date_range", fail)
    monkeypatch.setattr(service, "fetch_provenance_identifiers", fail)
    with service.dashboard_read_scope(demo_rows={"factures": [{"facture_id": "DEMO-001"}]}):
        assert service.charger_donnees("factures").iloc[0]["facture_id"] == "DEMO-001"
        metrics = query_metrics_snapshot()
        assert metrics["clients"] == metrics["selects"] == metrics["checks"] == 0
