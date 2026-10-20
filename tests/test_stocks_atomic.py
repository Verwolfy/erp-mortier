"""Tests du contrat Python, avec base Supabase simulée (pas de réseau)."""
from __future__ import annotations

import importlib.util
import sys
import types
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import pytest

SERVICE_FILE = Path(__file__).resolve().parents[1] / "modules" / "stocks" / "service.py"


@pytest.fixture
def stock(monkeypatch):
    """Isole le service des dépendances ERP, Streamlit et Supabase réelles."""
    reader = types.ModuleType("core.db_service")
    reader.fetch_data = Mock(side_effect=lambda t: [{"table": t}])
    reader.fetch_data_filtered = Mock(side_effect=lambda t, c, v: [{c: v}])
    reader.check_server_permission = Mock(return_value=True)
    core = types.ModuleType("core")
    monkeypatch.setitem(sys.modules, "core", core)
    monkeypatch.setitem(sys.modules, "core.db_service", reader)

    streamlit = types.ModuleType("streamlit")
    streamlit.secrets = {"supabase": {"url": "https://example.supabase.co", "stock_service_key": "server-test-key"}}
    streamlit.cache_resource = lambda **kwargs: lambda f: f
    monkeypatch.setitem(sys.modules, "streamlit", streamlit)

    api = types.ModuleType("supabase")
    api.Client = object
    api.create_client = Mock()
    monkeypatch.setitem(sys.modules, "supabase", api)

    spec = importlib.util.spec_from_file_location("tested_stock_module", SERVICE_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._stock_rpc_client_original = module._stock_rpc_client
    module._stock_rpc_client = Mock()
    client = module._stock_rpc_client.return_value
    client.rpc = Mock()
    def rpc(name, params):
        assert name == "erp_apply_stock_movement"
        return types.SimpleNamespace(
            execute=lambda: types.SimpleNamespace(data={"operation_id": params["p_operation_id"], "cost_total": "15.50", "quantity_remaining": "10"})
        )
    client.rpc.side_effect = rpc
    return module, reader, client, streamlit, api


@pytest.mark.parametrize("method,args,kind,direction,cost", [
    ("enregistrer_entree_mp", ("MP-1", 10, 1.23, "BR-1", "2027-06-01"), "MP", "ENTREE", "1.23"),
    ("enregistrer_sortie_mp", ("MP-1", 10, "OF-1"), "MP", "SORTIE", None),
    ("enregistrer_entree_pf", ("PF-1", 10, 2.31, "OF-1", "2027-06-01"), "PF", "ENTREE", "2.31"),
    ("enregistrer_sortie_pf", ("PF-1", 10, "BL-1"), "PF", "SORTIE", None),
])
def test_contract_and_single_rpc(stock, method, args, kind, direction, cost):
    mod, reader, client, *_ = stock
    result = getattr(mod, method)(*args, operation_id="OP-123")
    assert result == (15.5 if method == "enregistrer_sortie_mp" else None)
    assert client.rpc.call_count == 1
    args_rpc, _ = client.rpc.call_args
    p = args_rpc[1]
    assert p["p_item_type"] == kind
    assert p["p_direction"] == direction
    assert p["p_quantity"] == "10"
    assert p["p_unit_cost"] == cost
    assert p["p_operation_id"] == "OP-123"
    reader.check_server_permission.assert_called_once_with(
        "mouvements" if kind == "MP" else "mouvements_pf")


@pytest.mark.parametrize("bad", [0, -1, "NaN", float("inf"), float("-inf"), None, True, "abc", "", "-0.1", "1e9999"])
def test_rejects_invalid_quantities(stock, bad):
    mod, _, client, *_ = stock
    with pytest.raises(ValueError):
        mod.enregistrer_entree_mp("MP", bad, 1, "BR", "", operation_id="OP")
    client.rpc.assert_not_called()


@pytest.mark.parametrize("bad", [-1, "NaN", float("inf"), None, False, "missing"])
def test_rejects_invalid_costs(stock, bad):
    mod, _, client, *_ = stock
    with pytest.raises(ValueError):
        mod.enregistrer_entree_pf("SKU", 1, bad, "OF", "", operation_id="OP")
    client.rpc.assert_not_called()


def test_zero_cost_permitted(stock):
    mod, _, client, *_ = stock
    mod.enregistrer_entree_mp("MP", "1.2", 0, "BR", "")
    assert client.rpc.call_args.args[1]["p_unit_cost"] == "0"


@pytest.mark.parametrize("item,ref,op", [
    ("", "REF", "OP"), (None, "REF", "OP"), ("MP", "", "OP"),
    ("MP", None, "OP"), ("MP", "REF", ""), ("MP", "REF", "x" * 129),
])
def test_rejects_empty_identifiers(stock, item, ref, op):
    mod, _, client, *_ = stock
    with pytest.raises(ValueError):
        mod.enregistrer_sortie_mp(item, 1, ref, operation_id=op)
    client.rpc.assert_not_called()


def test_denies_user_before_rpc(stock):
    mod, reader, client, *_ = stock
    reader.check_server_permission.return_value = False
    with pytest.raises(PermissionError):
        mod.enregistrer_sortie_pf("SKU", 10, "BL")
    client.rpc.assert_not_called()


def test_denies_broken_permission_check(stock):
    mod, reader, client, *_ = stock
    reader.check_server_permission.side_effect = RuntimeError("Database down")
    with pytest.raises(RuntimeError):
        mod.enregistrer_sortie_pf("SKU", 10, "BL")
    client.rpc.assert_not_called()


def test_network_failure_has_stable_retry_key(stock):
    mod, _, client, *_ = stock
    client.rpc.side_effect = ConnectionError("token=confidential")
    with pytest.raises(mod.StockOperationError) as info:
        mod.enregistrer_sortie_mp("MP", 5, "OF", operation_id="MY-STABLE-ID")
    assert info.value.operation_id == "MY-STABLE-ID"
    assert "confidential" not in str(info.value)


def test_unknown_commit_status_retains_generated_key(stock):
    mod, _, client, *_ = stock
    client.rpc.side_effect = TimeoutError()
    with pytest.raises(mod.StockOperationError) as info:
        mod.enregistrer_sortie_pf("SKU", 5, "BL")
    assert info.value.operation_id.startswith("STK-")


@pytest.mark.parametrize("response", [None, [], {}, {"operation_id": "OTHER"}])
def test_bad_response_is_not_silently_successful(stock, response):
    mod, _, client, *_ = stock
    client.rpc.side_effect = lambda n, p: types.SimpleNamespace(
        execute=lambda: types.SimpleNamespace(data=response))
    with pytest.raises(mod.StockOperationError):
        mod.enregistrer_entree_mp("MP", 5, 1, "BR", "")


def test_decimal_cost_exactly_passed(stock):
    mod, _, client, *_ = stock
    mod.enregistrer_entree_mp("MP", Decimal("1.0000000000001"), Decimal("1.235005"), "BR", "")
    params = client.rpc.call_args.args[1]
    assert params["p_quantity"] == "1.0000000000001"
    assert params["p_unit_cost"] == "1.235005"


def test_missing_server_secret_fails_closed(stock):
    mod, _, _, st, api = stock
    del st.secrets["supabase"]["stock_service_key"]
    with pytest.raises(RuntimeError, match="stock_service_key"):
        mod._stock_rpc_client_original()


def test_getters_keep_old_signatures(stock):
    mod, reader, *_ = stock
    for name in ("get_stock_actuel_mp", "get_stock_actuel_pf", "get_mouvements", "get_mouvements_pf", "get_lots"):
        assert isinstance(getattr(mod, name)(), pd.DataFrame)
    assert mod.get_mouvements_by_mp("ABC").iloc[0]["mp_id"] == "ABC"
    assert mod.get_mouvements_pf_by_sku("SKU").iloc[0]["sku_id"] == "SKU"


def test_no_hybrid_write_is_used():
    source = SERVICE_FILE.read_text(encoding="utf-8")
    assert "insert_hybrid(" not in source
    assert "update_hybrid(" not in source


def test_sql_migration_restricts_public_execution():
    sql = (SERVICE_FILE.parents[2] / "sql" / "002_atomic_stock_movement.sql").read_text()
    assert "SECURITY INVOKER" in sql
    assert "REVOKE ALL ON FUNCTION public.erp_apply_stock_movement" in sql
    assert "FROM PUBLIC, anon, authenticated" in sql
    assert "GRANT EXECUTE" in sql
    assert "TO service_role" in sql
    assert "FOR UPDATE" in sql
    assert "pg_advisory_xact_lock" in sql
    assert "erp_stock_outbox" in sql


@pytest.mark.parametrize("bad_cost", [None, "NaN", "Infinity", "-2", "bad"])
def test_invalid_cost_response_must_fail(stock, bad_cost):
    mod, _, client, *_ = stock
    client.rpc.side_effect = lambda n, p: types.SimpleNamespace(execute=lambda: types.SimpleNamespace(
        data={"operation_id": p["p_operation_id"], "cost_total": bad_cost, "quantity_remaining": "0"}))
    with pytest.raises(mod.StockOperationError):
        mod.enregistrer_sortie_mp("MP", 1, "OF")


@pytest.mark.parametrize("remaining", [None, "NaN", "-0.01", "abc"])
def test_invalid_stock_response_must_fail(stock, remaining):
    mod, _, client, *_ = stock
    client.rpc.side_effect = lambda n, p: types.SimpleNamespace(execute=lambda: types.SimpleNamespace(
        data={"operation_id": p["p_operation_id"], "cost_total": "0", "quantity_remaining": remaining}))
    with pytest.raises(mod.StockOperationError):
        mod.enregistrer_sortie_pf("SKU", 1, "BL")
