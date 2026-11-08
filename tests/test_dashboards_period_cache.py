"""OPT-01 — cache de lectures datées, strictement borné au rendu Dashboards."""
from __future__ import annotations

import pytest

from modules.dashboards import service


START = "2026-11-01"
END = "2026-11-08"


def test_period_read_once_per_render_with_independent_frames(monkeypatch):
    calls = []

    def read(table, column, start, end):
        calls.append((table, column, start, end))
        return [{"date": START, "montant": 7, "details": {"code": "original"}}]

    monkeypatch.setattr(service, "fetch_data_by_date_range", read)
    with service.dashboard_read_scope():
        first = service._lire_periode("factures", "date", START, END)
        first.loc[0, "montant"] = 999
        first.loc[0, "details"]["code"] = "modifie"
        second = service._lire_periode("factures", "date", START, END)
        assert second.loc[0, "montant"] == 7
        assert second.loc[0, "details"]["code"] == "original"
    assert calls == [("factures", "date", START, END)]


def test_cache_is_reset_between_renders(monkeypatch):
    calls = []

    def read(*args):
        calls.append(args)
        return [{"num": len(calls)}]

    monkeypatch.setattr(service, "fetch_data_by_date_range", read)
    with service.dashboard_read_scope():
        assert service._lire_periode("factures", "date", START, END).loc[0, "num"] == 1
    with service.dashboard_read_scope():
        assert service._lire_periode("factures", "date", START, END).loc[0, "num"] == 2
    assert len(calls) == 2


def test_cache_never_spans_different_dates_tables_or_columns(monkeypatch):
    calls = []

    def read(*args):
        calls.append(args)
        return [{"num": len(calls)}]

    monkeypatch.setattr(service, "fetch_data_by_date_range", read)
    with service.dashboard_read_scope():
        service._lire_periode("factures", "date", START, END)
        service._lire_periode("factures", "date", START, "2026-11-09")
        service._lire_periode("reglements", "date", START, END)
        service._lire_periode("factures", "date_echeance", START, END)
        service._lire_periode("factures", "date", START, END)
    assert len(calls) == 4


def test_nested_scope_never_reuses_outer_scope(monkeypatch):
    calls = []

    def read(*args):
        calls.append(args)
        return [{"num": len(calls)}]

    monkeypatch.setattr(service, "fetch_data_by_date_range", read)
    with service.dashboard_read_scope():
        assert service._lire_periode("factures", "date", START, END).loc[0, "num"] == 1
        with service.dashboard_read_scope():
            assert service._lire_periode("factures", "date", START, END).loc[0, "num"] == 2
        assert service._lire_periode("factures", "date", START, END).loc[0, "num"] == 1
    assert len(calls) == 2


def test_failed_read_is_not_cached(monkeypatch):
    calls = []

    def read(*args):
        calls.append(args)
        raise PermissionError("Accès interdit")

    monkeypatch.setattr(service, "fetch_data_by_date_range", read)
    with service.dashboard_read_scope():
        with pytest.raises(PermissionError):
            service._lire_periode("factures", "date", START, END)
        with pytest.raises(PermissionError):
            service._lire_periode("factures", "date", START, END)
    assert len(calls) == 2


def test_without_scope_does_not_cache(monkeypatch):
    calls = []

    def read(*args):
        calls.append(args)
        return [{"num": len(calls)}]

    monkeypatch.setattr(service, "fetch_data_by_date_range", read)
    assert service._lire_periode("factures", "date", START, END).loc[0, "num"] == 1
    assert service._lire_periode("factures", "date", START, END).loc[0, "num"] == 2
    assert len(calls) == 2


def test_demo_mode_never_calls_supabase(monkeypatch):
    monkeypatch.setattr(
        service, "fetch_data_by_date_range",
        lambda *args: pytest.fail("Mode DEMO ne doit pas consulter Supabase"),
    )
    demo = {"factures": [
        {"date": "2026-11-01", "montant": 1},
        {"date": "2026-10-01", "montant": 2},
    ]}
    with service.dashboard_read_scope(demo_rows=demo):
        first = service._lire_periode("factures", "date", START, END)
        assert first["montant"].tolist() == [1]
        first.loc[0, "montant"] = 700
        assert service._lire_periode("factures", "date", START, END)["montant"].tolist() == [1]


def test_period_cache_does_not_alias_unfiltered_cache(monkeypatch):
    count = {"global": 0, "period": 0}

    def global_read(*args):
        count["global"] += 1
        return [{"montant": 33}]

    def period_read(*args):
        count["period"] += 1
        return [{"montant": 7}]

    monkeypatch.setattr(service, "fetch_data", global_read)
    monkeypatch.setattr(service, "fetch_data_by_date_range", period_read)
    with service.dashboard_read_scope():
        assert service.charger_donnees("factures").loc[0, "montant"] == 33
        assert service._lire_periode("factures", "date", START, END).loc[0, "montant"] == 7
        assert service.charger_donnees("factures").loc[0, "montant"] == 33
        assert service._lire_periode("factures", "date", START, END).loc[0, "montant"] == 7
    assert count == {"global": 1, "period": 1}
