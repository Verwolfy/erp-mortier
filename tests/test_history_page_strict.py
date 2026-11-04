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
