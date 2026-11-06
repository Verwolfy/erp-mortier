"""Campagne de pagination analytique : volumétrie et refus de troncature."""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

PATH = Path(__file__).resolve().parents[1] / "modules" / "production" / "cost_service.py"


@pytest.fixture
def svc(monkeypatch):
    db = types.ModuleType("core.db_service")
    db.check_server_read_permission = MagicMock(return_value=True)
    db.check_server_permission = MagicMock(return_value=True)
    stock = types.ModuleType("modules.stocks.service")
    stock._stock_rpc_client = MagicMock()
    monkeypatch.setitem(sys.modules, "core.db_service", db)
    monkeypatch.setitem(sys.modules, "modules.stocks.service", stock)
    spec = importlib.util.spec_from_file_location("_cost_pagination_suite", PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, db, stock._stock_rpc_client


class Query:
    def __init__(self, rows, calls=None):
        self.rows = rows
        self.calls = calls if calls is not None else []
        self.orders = []
        self.start = 0
        self.end = 0
        self.filters = []

    def select(self, *_a, **_kw):
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def order(self, column, **_kw):
        self.orders.append(column)
        return self

    def range(self, start, end):
        self.start, self.end = start, end
        self.calls.append((start, end))
        return self

    def execute(self):
        rows = self.rows
        if self.orders:
            rows = sorted(rows, key=lambda r: tuple(r.get(c) for c in self.orders))
        return types.SimpleNamespace(data=rows[self.start:self.end+1])


def test_fetch_all_1301_rows_without_cut(svc):
    mod, _, _ = svc
    q = Query([{"id": f"{i:05d}"} for i in range(1301)][::-1])
    result = mod._fetch_all(q, ("id",))
    assert len(result) == 1301
    assert result[0]["id"] == "00000"
    assert result[-1]["id"] == "01300"
    assert q.calls == [(0, 499), (500, 999), (1000, 1499)]


def test_exact_page_size_has_terminal_probe(svc):
    mod, _, _ = svc
    q = Query([{"id": i} for i in range(1000)])
    assert len(mod._fetch_all(q, ("id",))) == 1000
    assert q.calls == [(0, 499), (500, 999), (1000, 1499)]


def test_empty_query_single_request(svc):
    mod, _, _ = svc
    q = Query([])
    assert mod._fetch_all(q, ("id",)) == []
    assert q.calls == [(0, 499)]


def test_page_limits_validated(svc):
    mod, _, _ = svc
    for invalid in (True, -1, 0, 1001, "500"):
        with pytest.raises(ValueError):
            mod._fetch_all(Query([]), ("id",), page_size=invalid)
    with pytest.raises(ValueError):
        mod._fetch_all(Query([]), ())


def test_bound_rejects_incomplete_report(svc, monkeypatch):
    mod, _, _ = svc
    monkeypatch.setattr(mod, "_REPORT_MAX_ROWS", 1000)
    q = Query([{"id": i} for i in range(1001)])
    with pytest.raises(RuntimeError, match="potentiellement incomplet"):
        mod._fetch_all(q, ("id",))


def test_period_listing_still_newest_first_and_complete(svc):
    mod, _, client = svc
    rows = [
        {"period_id": f"P-{i:03d}", "date_debut": "2026-01-01" if i < 500 else "2026-11-01"}
        for i in range(1101)
    ]
    q = Query(rows)
    client.return_value.table.return_value = q
    periods = mod.list_periods()
    assert len(periods) == 1101
    assert periods[0]["date_debut"] == "2026-11-01"
    assert periods[-1]["date_debut"] == "2026-01-01"
    assert len(q.calls) == 3


def test_full_report_has_all_pages_for_all_seven_tables(svc):
    mod, _, client = svc
    layout = {
        "erp_cost_pools": ("pool_id", 1101),
        "erp_cost_drivers": ("of_id", 1203),
        "erp_cost_allocations": ("pool_id", 1307),
        "erp_cost_of_summary": ("of_id", 1023),
        "erp_cost_scf_reconciliation": ("pool_id", 1101),
        "erp_cost_of_validation_drift": ("of_id", 1150),
    }
    queries = {}
    for table, (key, size) in layout.items():
        rows = [{key: f"{i:05d}"} for i in range(size)]
        if table == "erp_cost_drivers":
            for row in rows:
                row["base_imputation"] = "UNITS"
        if table == "erp_cost_allocations":
            for row in rows:
                row["of_id"] = "OF-TEST"
        qs = Query(rows)
        queries[table] = qs

    client.return_value.table.side_effect = lambda table: queries[table]
    client.return_value.rpc.return_value.execute.return_value.data = {"audit_ok": True}
    result = mod.get_period_report("P-REPORT")
    for key, table in {
        "pools": "erp_cost_pools",
        "drivers": "erp_cost_drivers",
        "allocations": "erp_cost_allocations",
        "summaries": "erp_cost_of_summary",
        "scf_reconciliation": "erp_cost_scf_reconciliation",
        "validation_drift": "erp_cost_of_validation_drift",
    }.items():
        assert len(result[key]) == layout[table][1]
        assert len(queries[table].calls) >= 3
        assert queries[table].filters == [("period_id", "P-REPORT")]
    assert result["audit"] == {"audit_ok": True}


def test_report_failure_never_returns_partial_dict(svc):
    mod, _, client = svc
    class BrokenQuery(Query):
        def execute(self):
            if self.start >= 500:
                raise ConnectionError("page unavailable")
            return super().execute()
    client.return_value.table.side_effect = lambda _t: BrokenQuery([
        {"pool_id": f"{i:05d}"} for i in range(1001)
    ])
    with pytest.raises(ConnectionError, match="page unavailable"):
        mod.get_period_report("P-REPORT")
    client.return_value.rpc.assert_not_called()


def test_repeated_key_across_pages_is_rejected(svc):
    mod, _, _ = svc
    values = [{"id": f"{i:05d}"} for i in range(1000)]
    values.insert(500, {"id": "00499"})
    with pytest.raises(RuntimeError, match="instable"):
        mod._fetch_all(Query(values), ("id",))


def test_missing_pagination_key_is_rejected(svc):
    mod, _, _ = svc
    with pytest.raises(RuntimeError, match="manquante"):
        mod._fetch_all(Query([{"other": "B"}]), ("id",))


def test_null_page_response_fails_closed(svc):
    mod, _, _ = svc

    class NullPage(Query):
        def execute(self):
            return types.SimpleNamespace(data=None)

    with pytest.raises(RuntimeError, match="incomplet"):
        mod._fetch_all(NullPage([]), ("id",))


def test_non_monotonic_page_refused_without_partial_output(svc):
    mod, _, _ = svc

    class ShiftedPage(Query):
        def execute(self):
            result = super().execute()
            if self.start == 500:
                result.data = [{"id": "00100"}] + result.data[1:]
            return result

    with pytest.raises(RuntimeError, match="instable"):
        mod._fetch_all(ShiftedPage([{"id": f"{i:05d}"} for i in range(1300)]), ("id",))


def test_full_report_rejects_duplicate_second_page(svc):
    mod, _, client = svc

    class OverlappingQuery(Query):
        def execute(self):
            result = super().execute()
            if self.start == 500:
                result.data[0] = {"pool_id": "00499"}
            return result

    client.return_value.table.side_effect = lambda table: (
        OverlappingQuery([{"pool_id": f"{i:05d}"} for i in range(1001)])
        if table == "erp_cost_pools" else Query([]))
    with pytest.raises(RuntimeError, match="instable"):
        mod.get_period_report("P-REPORT")
    client.return_value.rpc.assert_not_called()


def test_report_selected_section_only_fetches_one_dataset(svc):
    mod, _, client = svc
    query = Query([{"pool_id": f"{i:05d}"} for i in range(1201)])
    client.return_value.table.return_value = query
    client.return_value.rpc.return_value.execute.return_value.data = {"audit_ok": False}
    result = mod.get_period_report("P-REPORT", sections=("pools",))
    assert len(result["pools"]) == 1201
    assert result["loaded_sections"] == ["pools"]
    for name in ("drivers", "allocations", "summaries",
                 "scf_reconciliation", "validation_drift"):
        assert result[name] == []
        assert name not in result["loaded_sections"]
    assert client.return_value.table.call_count == 1
    assert query.calls == [(0, 499), (500, 999), (1000, 1499)]
    client.return_value.rpc.assert_called_once()


@pytest.mark.parametrize("bad", ((), ("invalid",), "pools", ["pools", "unknown"], None))
def test_invalid_section_selection_fails_closed(svc, bad):
    mod, _, client = svc
    if bad is None:
        # None retains the backward compatible complete report.
        return
    with pytest.raises(ValueError, match="sections"):
        mod.get_period_report("P-REPORT", sections=bad)
    client.return_value.table.assert_not_called()


def test_explicit_multiple_sections_does_not_fetch_other_tables(svc):
    mod, _, client = svc
    names = []
    data = {
        "erp_cost_pools": Query([{"pool_id": "POOL-1"}]),
        "erp_cost_of_validation_drift": Query([{"of_id": "OF-1"}]),
    }
    def open_table(name):
        names.append(name)
        return data[name]
    client.return_value.table.side_effect = open_table
    client.return_value.rpc.return_value.execute.return_value.data = {"audit_ok": True}
    result = mod.get_period_report(
        "P-REPORT", sections=("pools", "validation_drift", "pools"))
    assert names == ["erp_cost_pools", "erp_cost_of_validation_drift"]
    assert result["loaded_sections"] == ["pools", "validation_drift"]
    assert len(result["pools"]) == 1
    assert len(result["validation_drift"]) == 1
