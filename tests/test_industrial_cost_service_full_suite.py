"""Unitaires approfondis du service couts industriels avec session et DB simulees."""
from __future__ import annotations
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

PATH = Path(__file__).resolve().parents[1] / "modules" / "production" / "cost_service.py"
VALID_UUID = "11111111-1111-4111-8111-111111111111"


@pytest.fixture
def world(monkeypatch):
    db = types.ModuleType("core.db_service")
    db.check_server_permission = MagicMock(return_value=True)
    db.check_server_read_permission = MagicMock(return_value=True)
    client = MagicMock()
    tables = {}
    for name, data in {
        "erp_cost_periods": [{"statut": "BROUILLON",
                              "date_debut": "2026-11-01", "date_fin": "2026-11-30"}],
        "erp_cost_pools": [{"pool_id": "POOL-1", "statut": "SIMULATION",
                            "montant_dzd": "120.000000"}],
        "scf_pieces": [{"piece_id": VALID_UUID, "statut": "VALIDEE",
                         "date_validation": "2026-11-05T10:00:00Z"}],
        "scf_lignes": [{"ligne_id": 42, "piece_id": VALID_UUID,
                         "debit": "200", "credit": "0"}],
        "ordres_fabrication": [{"of_id": "OF-1", "statut": "TERMINE",
                                "date_fin": "2026-11-05"}],
        "erp_cost_pool_scf_evidence": [],
        "erp_cost_drivers": [],
    }.items():
        table = MagicMock(name=name)
        for method in ("select", "eq", "limit", "order", "insert", "upsert", "update"):
            getattr(table, method).return_value = table
        table.execute.return_value = types.SimpleNamespace(data=data)
        tables[name] = table
    client.table.side_effect = lambda name: tables[name]
    stock = types.ModuleType("modules.stocks.service")
    stock._stock_rpc_client = MagicMock(return_value=client)
    monkeypatch.setitem(sys.modules, "core.db_service", db)
    monkeypatch.setitem(sys.modules, "modules.stocks.service", stock)
    spec = importlib.util.spec_from_file_location("_cost_service_full_suite", PATH)
    service = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(service)
    return types.SimpleNamespace(service=service, db=db, client=client, tables=tables)


def test_both_write_permissions_mandatory(world):
    world.db.check_server_permission.side_effect = lambda t: t != "comptes"
    assert world.service.can_manage_costs() is False
    with pytest.raises(PermissionError):
        world.service.create_nature("ENERGIE2", "Energie")
    world.client.table.assert_not_called()


def test_limited_read_denied_before_service_key(world):
    world.db.check_server_read_permission.side_effect = lambda t: t != "comptes"
    with pytest.raises(PermissionError):
        world.service.get_period_report("P-1")
    world.client.table.assert_not_called()


def test_writer_access_confirmed(world):
    assert world.service.can_manage_costs() is True
    world.db.check_server_permission.assert_any_call("ordres_fabrication")
    world.db.check_server_permission.assert_any_call("comptes")


@pytest.mark.parametrize("bad", ("wrong-uuid", "", "123", None))
def test_document_invalid_uuid_never_writes(world, bad):
    with pytest.raises(ValueError):
        world.service.document_pool("P-1", "POOL-1", bad, 42, "Imputation fictive")
    world.tables["erp_cost_pool_scf_evidence"].upsert.assert_not_called()


@pytest.mark.parametrize("line", (0, -1, True, 1.2, "42"))
def test_document_invalid_line_id_never_writes(world, line):
    with pytest.raises(ValueError):
        world.service.document_pool("P-1", "POOL-1", VALID_UUID, line, "Imputation fictive")
    world.tables["erp_cost_pool_scf_evidence"].upsert.assert_not_called()


@pytest.mark.parametrize("reason", ("", "court", "x" * 1001))
def test_document_missing_explanation_never_writes(world, reason):
    with pytest.raises(ValueError):
        world.service.document_pool("P-1", "POOL-1", VALID_UUID, 42, reason)
    world.tables["erp_cost_pool_scf_evidence"].upsert.assert_not_called()


def test_document_rejects_unapproved_scf_piece(world):
    world.tables["scf_pieces"].execute.return_value.data = [
        {"piece_id": VALID_UUID, "statut": "BROUILLON", "date_validation": None}]
    with pytest.raises(ValueError, match="SCF"):
        world.service.document_pool("P-1", "POOL-1", VALID_UUID, 42, "Motif documente")
    world.tables["erp_cost_pool_scf_evidence"].upsert.assert_not_called()


def test_document_rejects_wrong_scf_line(world):
    world.tables["scf_lignes"].execute.return_value.data = []
    with pytest.raises(ValueError, match="Ligne SCF"):
        world.service.document_pool("P-1", "POOL-1", VALID_UUID, 42, "Motif documente")
    world.tables["erp_cost_pool_scf_evidence"].upsert.assert_not_called()


@pytest.mark.parametrize("debit", ("0", "-2", "NaN", "99"))
def test_document_rejects_insufficient_debit(world, debit):
    world.tables["scf_lignes"].execute.return_value.data[0]["debit"] = debit
    with pytest.raises(ValueError):
        world.service.document_pool("P-1", "POOL-1", VALID_UUID, 42, "Motif documente")
    world.tables["erp_cost_pool_scf_evidence"].upsert.assert_not_called()


def test_document_success_writes_evidence_then_status(world):
    world.service.document_pool("P-1", "POOL-1", VALID_UUID, 42, "Energie de fabrication")
    evidence = world.tables["erp_cost_pool_scf_evidence"]
    evidence.upsert.assert_called_once()
    payload = evidence.upsert.call_args.args[0]
    assert payload == {
        "pool_id": "POOL-1", "piece_id": VALID_UUID,
        "scf_ligne_id": 42, "explication_imputation": "Energie de fabrication",
    }
    pool = world.tables["erp_cost_pools"]
    pool.update.assert_called_once()
    assert pool.update.call_args.args[0]["statut"] == "DOCUMENTE"


def test_document_denies_after_period_validation(world):
    world.tables["erp_cost_periods"].execute.return_value.data = [{"statut": "VALIDE"}]
    with pytest.raises(ValueError, match="non modifiable"):
        world.service.document_pool("P-1", "POOL-1", VALID_UUID, 42, "Motif documente")
    world.tables["erp_cost_pool_scf_evidence"].upsert.assert_not_called()


@pytest.mark.parametrize("state", ("EN_COURS", "REJETE"))
def test_measure_rejects_unfinished_of(world, state):
    world.tables["ordres_fabrication"].execute.return_value.data[0]["statut"] = state
    with pytest.raises(ValueError):
        world.service.set_driver("P-1", "OF-1", "KWH", "12", "Relevé")
    world.tables.setdefault("erp_cost_drivers", MagicMock()).upsert.assert_not_called()


def test_measure_rejects_of_outside_period(world):
    world.tables["ordres_fabrication"].execute.return_value.data[0]["date_fin"] = "2026-12-05"
    with pytest.raises(ValueError, match="hors période"):
        world.service.set_driver("P-1", "OF-1", "KWH", "12", "Relevé")


def test_measure_rejects_unknown_basis(world):
    with pytest.raises(ValueError):
        world.service.set_driver("P-1", "OF-1", "MINUTES", "12", "Relevé")


def test_amount_must_be_exact_finite_and_precise(world):
    for bad in ("NaN", "Infinity", "-1", "1e16", "0.0000001", True):
        with pytest.raises(ValueError):
            world.service._amount(bad, "Montant")
    assert world.service._amount("10.123456", "Montant") == "10.123456"
