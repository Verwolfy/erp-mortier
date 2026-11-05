"""Filtre historique SQL : période, pagination, confidentialité et erreurs."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from core import strict_reads as reads


class Query:
    def __init__(self, call_log):
        self.calls = call_log
        self.filters = []
        self.sort = []
        self.bounds = None

    def select(self, projection, *, count):
        assert count == "exact"
        return self

    def gte(self, field, value):
        self.filters.append(("gte", field, value))
        return self

    def lte(self, field, value):
        self.filters.append(("lte", field, value))
        return self

    def order(self, column, *, desc=False, nullsfirst=None):
        self.sort.append((column, desc))
        return self

    def range(self, low, high):
        self.bounds = (low, high)
        return self

    def execute(self):
        self.calls.append((self.filters[:], self.sort[:], self.bounds))
        return SimpleNamespace(
            data=[{"commande_achat_id": "CA-2", "date_commande": "2026-11-03"}],
            count=1)


def test_period_applied_before_range_and_totals(monkeypatch):
    calls, guard = [], Mock()
    monkeypatch.setattr(reads.db, "_require_read_permission", guard)
    monkeypatch.setattr(reads.db, "get_supabase_client",
                        lambda: SimpleNamespace(table=lambda _: Query(calls)))
    rows, count = reads.fetch_history_page_strict(
        "commandes_achats", date_column="date_commande",
        start_date="2026-11-01", end_date="2026-11-05")
    assert count == 1 and len(rows) == 1
    assert calls == [(
        [("gte", "date_commande", "2026-11-01"),
         ("lte", "date_commande", "2026-11-05")],
        [("date_commande", True), ("commande_achat_id", True)],
        (0, 49),
    )]
    guard.assert_called_once_with("commandes_achats")


@pytest.mark.parametrize("kwargs", [
    {"start_date": "2026-11-01", "end_date": "2026-11-05"},
    {"date_column": "date_commande", "start_date": "2026-11-01"},
    {"date_column": "date_commande", "end_date": "2026-11-05"},
    {"date_column": "date_commande", "start_date": "2026-13-01", "end_date": "2026-11-05"},
    {"date_column": "date_commande", "start_date": "2026-11-10", "end_date": "2026-11-01"},
    {"date_column": "hash_mdp", "start_date": "2026-11-01", "end_date": "2026-11-05"},
    {"date_column": "date_commande", "start_date": True, "end_date": "2026-11-05"},
])
def test_invalid_period_never_queries(monkeypatch, kwargs):
    call = Mock(side_effect=AssertionError("Connection should not occur"))
    monkeypatch.setattr(reads.db, "get_supabase_client", call)
    with pytest.raises(ValueError):
        reads.fetch_history_page_strict("commandes_achats", **kwargs)
    call.assert_not_called()


def test_invalid_ui_period_never_returns_range(monkeypatch):
    import core.history_filters as periods
    monkeypatch.setattr(periods.st, "checkbox", lambda *a, **k: True)
    monkeypatch.setattr(periods.st, "date_input",
                        lambda label, **kw: __import__("datetime").date(2026, 11, 10)
                        if label == "Du" else __import__("datetime").date(2026, 11, 1))
    errors = []
    monkeypatch.setattr(periods.st, "error", errors.append)
    assert periods.history_period_inputs("test") is None
    assert len(errors) == 1


def test_inactive_ui_filter_is_empty(monkeypatch):
    import core.history_filters as periods
    monkeypatch.setattr(periods.st, "checkbox", lambda *a, **k: False)
    assert periods.history_period_inputs("test") == {}
