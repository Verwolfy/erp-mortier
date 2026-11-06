"""Contrat du précontrôle analytique : lecture seule et écriture confirmée.

Tous les jeux de données sont fictifs et fournis par des doublures ; aucun
secret, RPC SQL réel ou serveur de production n'est utilisé.
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

PATH = Path(__file__).resolve().parents[1] / "modules/production/cost_service.py"
SECTIONS = ["pools", "drivers", "scf_reconciliation", "summaries"]


@pytest.fixture
def env(monkeypatch):
    db = types.ModuleType("core.db_service")
    db.check_server_read_permission = MagicMock(return_value=True)
    db.check_server_permission = MagicMock(return_value=True)

    client = MagicMock()
    tables = {}
    for table_name, data in {
        "erp_cost_periods": [{
            "period_id": "P-TEST", "statut": "BROUILLON",
            "date_debut": "2026-11-01", "date_fin": "2026-11-30",
        }],
        "ordres_fabrication": [{"of_id": "OF-TEST", "date_fin": "2026-11-05",
                               "statut": "TERMINE"}],
        "erp_cost_pools": [],
        "erp_cost_drivers": [],
        "erp_cost_natures": [],
    }.items():
        t = MagicMock(name=table_name)
        for name in ("select", "eq", "gte", "lte", "order", "limit", "range",
                     "insert", "upsert"):
            getattr(t, name).return_value = t
        t.execute.return_value = types.SimpleNamespace(data=data)
        tables[table_name] = t
    client.table.side_effect = lambda name: tables[name]

    stock = types.ModuleType("modules.stocks.service")
    stock._stock_rpc_client = MagicMock(return_value=client)
    monkeypatch.setitem(sys.modules, "core.db_service", db)
    monkeypatch.setitem(sys.modules, "modules.stocks.service", stock)
    spec = importlib.util.spec_from_file_location("_cost_preflight_test", PATH)
    service = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(service)
    report = {
        "loaded_sections": SECTIONS,
        "audit_calculated": True,
        "pools": [{"pool_id": "POOL-TEST", "statut": "DOCUMENTE"}],
        "drivers": [{"of_id": "OF-TEST", "base_imputation": "KWH", "valeur": "10"}],
        "scf_reconciliation": [{
            "pool_id": "POOL-TEST", "rapprochement_ok": True,
            "montant_debit_scf_dzd": "200",
        }],
        "summaries": [{"of_id": "OF-TEST"}],
        "audit": {"audit_ok": True, "pools_sans_assiette": 0,
                  "of_hors_periode_ou_non_termines": 0,
                  "total_pools_dzd": 100, "total_impute_dzd": 100},
    }
    service.get_period_report = MagicMock(return_value=report)
    return types.SimpleNamespace(svc=service, db=db, client=client,
                                 tables=tables, report=report)


def test_ready_requires_complete_scf_and_audit(env):
    result = env.svc.get_validation_preflight("P-TEST")
    assert result["ready"] is True
    assert result["blockers"] == []
    assert result["counts"] == {
        "charges": 1, "assiettes": 1, "charges_documentees": 1,
        "of_analyses": 1, "of_termines_dans_periode": 1,
    }
    env.svc.get_period_report.assert_called_once_with(
        "P-TEST", sections=tuple(SECTIONS), include_audit=True)
    env.client.rpc.assert_not_called()
    for t in env.tables.values():
        t.insert.assert_not_called()
        t.upsert.assert_not_called()


def test_zero_equals_zero_cannot_validate_empty_period(env):
    env.report.update({
        "pools": [], "drivers": [], "scf_reconciliation": [], "summaries": [],
    })
    env.tables["ordres_fabrication"].execute.return_value.data = []
    env.report["audit"].update({
        "audit_ok": True, "total_pools_dzd": 0, "total_impute_dzd": 0,
    })
    result = env.svc.get_validation_preflight("P-TEST")
    assert result["ready"] is False
    assert result["audit_equilibre"] is True
    assert result["counts"]["charges"] == 0
    assert any("Aucune charge" in s for s in result["blockers"])
    assert any("Aucun OF terminé" in s for s in result["blockers"])


def test_unvalidated_scf_blocks_even_if_math_is_balanced(env):
    env.report["scf_reconciliation"][0]["rapprochement_ok"] = False
    result = env.svc.get_validation_preflight("P-TEST")
    assert result["ready"] is False
    assert result["counts"]["charges_documentees"] == 0
    assert any("pièce SCF validée" in s for s in result["blockers"])


def test_non_compliant_audit_blocks_even_with_documented_costs(env):
    env.report["audit"]["audit_ok"] = False
    env.report["audit"]["of_hors_periode_ou_non_termines"] = 1
    result = env.svc.get_validation_preflight("P-TEST")
    assert result["ready"] is False
    assert any("hors des dates" in s for s in result["blockers"])


def test_validated_period_is_not_revalidated(env):
    env.tables["erp_cost_periods"].execute.return_value.data[0]["statut"] = "VALIDE"
    result = env.svc.get_validation_preflight("P-TEST")
    assert result["ready"] is False
    assert any("plus en brouillon" in s for s in result["blockers"])


@pytest.mark.parametrize("fault", ["missing", "duplicated", "noaudit", "wrongsections"])
def test_incomplete_or_inconsistent_reads_fail_closed(env, fault):
    if fault == "missing":
        env.tables["erp_cost_periods"].execute.return_value.data = []
    elif fault == "duplicated":
        env.report["scf_reconciliation"].append(
            {"pool_id": "POOL-TEST", "rapprochement_ok": True})
    elif fault == "noaudit":
        env.report["audit"] = None
    else:
        env.report["loaded_sections"] = ["pools"]
    with pytest.raises(RuntimeError):
        env.svc.get_validation_preflight("P-TEST")


def test_preflight_requires_finance_and_production_before_opening_server_client(env):
    env.db.check_server_read_permission.side_effect = lambda table: table != "comptes"
    with pytest.raises(PermissionError):
        env.svc.get_validation_preflight("P-TEST")
    env.client.table.assert_not_called()


@pytest.mark.parametrize("rows", [None, [], [{"id": "wrong"}],
                                  [{"id": "good"}, {"id": "good"}]])
def test_unconfirmed_write_rejected(rows, env):
    with pytest.raises(RuntimeError, match="non confirmée"):
        env.svc._confirmed_row(types.SimpleNamespace(data=rows), {"id": "good"})


def test_confirmed_write_accepts_exact_single_record(env):
    env.svc._confirmed_row(types.SimpleNamespace(
        data=[{"period_id": "P-1", "statut": "BROUILLON"}]),
        {"period_id": "P-1", "statut": "BROUILLON"})


def test_period_insert_returns_id_only_after_confirmation(env, monkeypatch):
    monkeypatch.setattr(env.svc, "uuid4", lambda: "known")
    env.tables["erp_cost_periods"].execute.return_value.data = [
        {"period_id": "COST-P-known", "statut": "BROUILLON"}]
    assert env.svc.create_period("Novembre", "2026-11-01", "2026-11-30") == "COST-P-known"
    env.tables["erp_cost_periods"].execute.return_value.data = []
    with pytest.raises(RuntimeError, match="non confirmée"):
        env.svc.create_period("Novembre", "2026-11-01", "2026-11-30")


def test_pool_insert_requires_matching_database_echo(env, monkeypatch):
    monkeypatch.setattr(env.svc, "uuid4", lambda: "pool-id")
    env.tables["erp_cost_pools"].execute.return_value.data = [{
        "pool_id": "COST-POOL-pool-id", "period_id": "P-TEST",
        "statut": "SIMULATION",
    }]
    assert env.svc.add_pool("P-TEST", "ENERGIE", "KWH", "100.25", "Pièce") == "COST-POOL-pool-id"
    env.tables["erp_cost_pools"].execute.return_value.data = []
    with pytest.raises(RuntimeError, match="non confirmée"):
        env.svc.add_pool("P-TEST", "ENERGIE", "KWH", "100.25", "Pièce")


def test_driver_upsert_requires_matching_database_echo(env):
    env.tables["erp_cost_drivers"].execute.return_value.data = [{
        "period_id": "P-TEST", "of_id": "OF-TEST", "base_imputation": "KWH",
    }]
    env.svc.set_driver("P-TEST", "OF-TEST", "KWH", "10", "Relevé")
    env.tables["erp_cost_drivers"].execute.return_value.data = []
    with pytest.raises(RuntimeError, match="non confirmée"):
        env.svc.set_driver("P-TEST", "OF-TEST", "KWH", "10", "Relevé")


def test_nature_insert_requires_database_echo(env):
    env.tables["erp_cost_natures"].execute.return_value.data = [
        {"nature_code": "TEST_NATURE", "actif": True}]
    env.svc.create_nature("TEST_NATURE", "Nature de test")
    env.tables["erp_cost_natures"].execute.return_value.data = []
    with pytest.raises(RuntimeError, match="non confirmée"):
        env.svc.create_nature("TEST_NATURE", "Nature de test")
