"""Security contract: industrial-cost APIs never trust client role or bypass server checks."""
from __future__ import annotations
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

PATH = Path(__file__).resolve().parents[1] / "modules" / "production" / "cost_service.py"


@pytest.fixture
def service(monkeypatch):
    db = types.ModuleType("core.db_service")
    db.check_server_permission = MagicMock(return_value=False)
    db.check_server_read_permission = MagicMock(return_value=False)
    stock = types.ModuleType("modules.stocks.service")
    client = MagicMock()
    stock._stock_rpc_client = MagicMock(return_value=client)
    for key, module in {
        "core.db_service": db, "modules.stocks.service": stock,
    }.items():
        monkeypatch.setitem(sys.modules, key, module)
    spec = importlib.util.spec_from_file_location("_isolated_cost_service", PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, db, client


def test_unauthorized_read_never_reaches_service_key(service):
    mod, db, client = service
    with pytest.raises(PermissionError):
        mod.list_periods()
    with pytest.raises(PermissionError):
        mod.list_natures()
    with pytest.raises(PermissionError):
        mod.get_period_report("PERIOD-X")
    client.table.assert_not_called()


def test_missing_finance_permission_denies_write(service):
    mod, db, client = service
    db.check_server_permission.side_effect = lambda table: table == "ordres_fabrication"
    with pytest.raises(PermissionError):
        mod.create_period("Novembre", "2026-11-01", "2026-11-30")
    with pytest.raises(PermissionError):
        mod.add_pool("PERIOD-X", "ENERGIE", "KWH", "100", "FACT-123")
    client.table.assert_not_called()


def test_invalid_monetary_values_rejected_before_sql(service):
    mod, _, _ = service
    for val in (True, "NaN", "Infinity", "-1", "0.0000001", "1e15"):
        with pytest.raises(ValueError):
            mod._amount(val, "Montant")
    assert mod._amount("123.456789", "Montant") == "123.456789"


def test_service_only_reads_if_both_read_permissions_exist(service):
    mod, db, client = service
    db.check_server_read_permission.side_effect = lambda table: table == "ordres_fabrication"
    with pytest.raises(PermissionError):
        mod.list_periods()
    client.table.assert_not_called()


def test_authorized_period_creation_uses_brouillon(service):
    mod, db, client = service
    db.check_server_permission.return_value = True
    period_id = mod.create_period("Novembre", "2026-11-01", "2026-11-30")
    assert period_id.startswith("COST-P-")
    payload = client.table.return_value.insert.call_args.args[0]
    assert payload["statut"] == "BROUILLON"
    assert payload["date_debut"] == "2026-11-01"
    assert payload["date_fin"] == "2026-11-30"
