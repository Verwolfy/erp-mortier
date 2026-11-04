"""Pagination historique : exactitude, refus RBAC et absence de troncature."""
from types import SimpleNamespace

import pytest

from core import strict_reads as reads


class FakeQuery:
    def __init__(self, response, calls):
        self.response, self.calls = response, calls
        self.projection = self.key = None
        self.bounds = None

    def select(self, projection, *, count):
        assert count == "exact"
        self.projection = projection
        return self

    def order(self, key, *, desc=False):
        assert desc is True
        self.key = key
        return self

    def range(self, low, high):
        self.bounds = (low, high)
        return self

    def execute(self):
        self.calls.append((self.key, self.bounds, self.projection))
        return self.response


def test_page_boundaries_total_and_rbac(monkeypatch):
    calls, grants = [], []
    response = SimpleNamespace(
        data=[{"interaction_id": "INT-009"}, {"interaction_id": "INT-008"}],
        count=12)
    monkeypatch.setattr(reads.db, "_require_read_permission", lambda table: grants.append(table))
    monkeypatch.setattr(reads.db, "get_supabase_client", lambda: SimpleNamespace(
        table=lambda table: FakeQuery(response, calls)))
    rows, total = reads.fetch_history_page_strict(
        "interactions", page=2, page_size=2)
    assert total == 12 and len(rows) == 2
    assert calls[0][0] == "interaction_id"
    assert calls[0][1] == (2, 3)
    assert grants == ["interactions"]


@pytest.mark.parametrize("response", [
    SimpleNamespace(data=None, count=0),
    SimpleNamespace(data=[], count=None),
    SimpleNamespace(data=[], count=4),
    SimpleNamespace(data=[{"interaction_id": ""}], count=1),
    SimpleNamespace(data=[{"interaction_id": "X"}, {"interaction_id": "X"}], count=2),
    SimpleNamespace(data=[{"interaction_id": "X"}], count=100001),
])
def test_bad_pages_fail_closed(monkeypatch, response):
    monkeypatch.setattr(reads.db, "_require_read_permission", lambda table: None)
    monkeypatch.setattr(reads.db, "get_supabase_client", lambda: SimpleNamespace(
        table=lambda table: FakeQuery(response, [])))
    with pytest.raises(reads.DataReadError):
        reads.fetch_history_page_strict("interactions", page_size=2)


def test_permission_denial_precedes_data_access(monkeypatch):
    def deny(table):
        raise PermissionError("Access denied")
    monkeypatch.setattr(reads.db, "_require_read_permission", deny)
    monkeypatch.setattr(reads.db, "get_supabase_client",
                        lambda: (_ for _ in ()).throw(AssertionError("unexpected request")))
    with pytest.raises(PermissionError):
        reads.fetch_history_page_strict("interactions")


@pytest.mark.parametrize("settings", [
    {"page": 0}, {"page": True}, {"page": 1001},
    {"page_size": 0}, {"page_size": 101}, {"page_size": True},
])
def test_invalid_page_refused(settings):
    with pytest.raises(ValueError):
        reads.fetch_history_page_strict("interactions", **settings)


def test_service_wrappers_keep_total(monkeypatch):
    from modules.crm import service as crm
    from modules.production import service as prod
    monkeypatch.setattr(reads, "fetch_history_page_strict",
                        lambda table, **kw: ([{"interaction_id": "X"}], 37))
    frame, total = crm.get_interactions_page(page=3)
    assert total == 37 and len(frame) == 1
    frame, total = prod.get_consommations_of_page(page=3)
    assert total == 37 and len(frame) == 1


def test_chronological_order_uses_date_then_primary_key(monkeypatch):
    queries, guards = [], []
    class HistoryQuery(FakeQuery):
        def __init__(self):
            super().__init__(SimpleNamespace(
                data=[{"mouvement_id": "M2", "date": "2026-11-04"}], count=1), queries)
            self.orders = []
        def order(self, key, *, desc=False, nullsfirst=None):
            self.orders.append((key, desc, nullsfirst))
            return self
        def execute(self):
            queries.append((tuple(self.orders), self.bounds))
            return self.response
    monkeypatch.setattr(reads.db, "_require_read_permission", lambda table: guards.append(table))
    monkeypatch.setattr(reads.db, "get_supabase_client",
                        lambda: SimpleNamespace(table=lambda _: HistoryQuery()))
    rows, total = reads.fetch_history_page_strict(
        "mouvements", date_column="date")
    assert total == 1 and rows[0]["mouvement_id"] == "M2"
    assert queries == [((("date", True, False),
                         ("mouvement_id", True, None)), (0, 49))]
    assert guards == ["mouvements"]


@pytest.mark.parametrize("date_column", ["hash_mdp", "not_a_column", "", 42])
def test_invalid_chronological_column_rejected_without_network(monkeypatch, date_column):
    monkeypatch.setattr(
        reads.db, "get_supabase_client",
        lambda: (_ for _ in ()).throw(AssertionError("Ne doit pas contacter la DB")))
    with pytest.raises(ValueError):
        reads.fetch_history_page_strict("mouvements", date_column=date_column)


def test_technical_order_remains_available_for_undated_history():
    from pathlib import Path
    production = Path("modules/production/service.py").read_text(encoding="utf-8")
    assert '"consommations_of", page=page, page_size=page_size)' in production


def test_business_date_sort_is_explicit_in_historical_views():
    from pathlib import Path
    cases = {
        "modules/stocks/views.py": ['date_column="date"'],
        "modules/achats/views.py": [
            'date_column="date_commande"', 'date_column="date_reception"'],
        "modules/ventes/views.py": ['date_column="date"'],
        "modules/crm/service.py": ['date_column="date_creation"'],
        "modules/production/service.py": ['date_column="date"'],
    }
    for path, examples in cases.items():
        text = Path(path).read_text(encoding="utf-8")
        for expected in examples:
            assert expected in text, f"{path} sans {expected}"
