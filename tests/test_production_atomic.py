"""Tests isolated, no Supabase network or production writes."""
from __future__ import annotations

import importlib.util
import sys
import types
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import pytest

BASE = Path(__file__).resolve().parents[1]
SCRIPT = BASE / "modules" / "production" / "service.py"
SQL = BASE / "sql" / "003_atomic_manufacturing_close.sql"


@pytest.fixture
def scenario(monkeypatch):
    core = types.ModuleType("core")
    database = types.ModuleType("core.db_service")
    database.check_server_permission = Mock(return_value=True)
    database.fetch_data = Mock(return_value=[])
    database.fetch_data_filtered = Mock(return_value=[])
    database.insert_hybrid = Mock(return_value=[{"ok": True}])
    database.update_hybrid = Mock(return_value=[{"ok": True}])
    util = types.ModuleType("core.utils")
    util.generate_unique_id = Mock(side_effect=lambda prefix, ids: prefix + "-0001")
    util.generate_technical_id = Mock(side_effect=lambda prefix: prefix + "-abc")
    util.get_local_now = Mock()
    stock_service = types.ModuleType("modules.stocks.service")
    stock_service._stock_rpc_client = Mock()
    rclient = stock_service._stock_rpc_client.return_value
    def rpc(name, params):
        if name == "erp_create_recipe":
            data = {"recette_id": "REC-0001", "operation_id": params["p_operation_id"],
                    "nb_lignes": len(params["p_lignes"])}
        elif name == "erp_create_manufacturing_order":
            data = {"of_id": "OF-0001", "operation_id": params["p_operation_id"],
                    "statut": "PLANIFIE"}
        else:
            data = {"of_id": params["p_of_id"],
                    "statut": "TERMINE" if params["p_conforme"] == "OUI" else "REJETE",
                    "cout_total": 150, "nb_consommations": 2}
        return types.SimpleNamespace(execute=lambda: types.SimpleNamespace(data=data))
    rclient.rpc.side_effect = rpc
    for name, mod in [("core", core), ("core.db_service", database),
                      ("core.utils", util), ("modules", types.ModuleType("modules")),
                      ("modules.stocks", types.ModuleType("modules.stocks")),
                      ("modules.stocks.service", stock_service)]:
        monkeypatch.setitem(sys.modules, name, mod)
    spec = importlib.util.spec_from_file_location("test_of_module", SCRIPT)
    service = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(service)
    return service, database, stock_service, rclient, util


def close(service, **kw):
    args = dict(of_id="OF-001", conforme="OUI", remarques="Conforme", controleur="laboratoire",
                quantite_produite="500", emballage_mp_id=None, emballage_consomme=0)
    args.update(kw)
    return service.enregistrer_controle_qualite(**args)


def test_one_rpc_for_whole_of(scenario):
    service, db, stock, client, _ = scenario
    ret = close(service)
    assert ret["statut"] == "TERMINE"
    assert ret["of_id"] == "OF-001"
    assert client.rpc.call_count == 1
    assert client.rpc.call_args.args[0] == "erp_close_manufacturing_order"
    args = client.rpc.call_args.args[1]
    assert args["p_quantite_produite"] == "500"
    assert args["p_remarques"] == "Conforme"
    assert args["p_emballage_mp_id"] is None
    db.insert_hybrid.assert_not_called()
    db.update_hybrid.assert_not_called()
    db.check_server_permission.assert_any_call("controle_qualite")
    db.check_server_permission.assert_any_call("mouvements")
    db.check_server_permission.assert_any_call("mouvements_pf")


def test_packaging_inputs(scenario):
    svc, _, _, client, _ = scenario
    close(svc, emballage_mp_id="SAC-25KG", emballage_consomme=20)
    kw = client.rpc.call_args.args[1]
    assert kw["p_emballage_mp_id"] == "SAC-25KG"
    assert kw["p_emballage_consomme"] == "20"


def test_packaging_decimal_precision(scenario):
    svc, _, _, client, _ = scenario
    close(svc, quantite_produite=Decimal("1.125"), emballage_mp_id="BOITE", emballage_consomme=Decimal("0.125"))
    kw = client.rpc.call_args.args[1]
    assert kw["p_quantite_produite"] == "1.125"
    assert kw["p_emballage_consomme"] == "0.125"


def test_quality_rejected_records_only_one_rpc(scenario):
    svc, db, _, client, _ = scenario
    ret = close(svc, conforme="NON", quantite_produite=0)
    assert ret["statut"] == "REJETE"
    assert client.rpc.call_count == 1
    db.check_server_permission.assert_called_once_with("controle_qualite")


@pytest.mark.parametrize("bad", ["", " ", None, True, 123, "x" * 201])
def test_of_id_invalid(scenario, bad):
    svc, _, _, client, _ = scenario
    with pytest.raises(ValueError):
        close(svc, of_id=bad)
    client.rpc.assert_not_called()


@pytest.mark.parametrize("bad", ["", " ", None, True, {}, "x" * 201])
def test_controleur_invalid(scenario, bad):
    svc, _, _, client, _ = scenario
    with pytest.raises(ValueError):
        close(svc, controleur=bad)
    client.rpc.assert_not_called()


@pytest.mark.parametrize("bad", [None, 3, {}, "x" * 5001])
def test_remarques_invalid(scenario, bad):
    svc, _, _, client, _ = scenario
    with pytest.raises(ValueError):
        close(svc, remarques=bad)
    client.rpc.assert_not_called()


@pytest.mark.parametrize("bad", ["NON ", "oui", "1", True, None, "", "REJETE"])
def test_conforme_invalid(scenario, bad):
    svc, _, _, client, _ = scenario
    with pytest.raises(ValueError):
        close(svc, conforme=bad)
    client.rpc.assert_not_called()


@pytest.mark.parametrize("bad", [0, -1, None, True, False, "bad", "NaN", float("inf"), "1e15", "1e9999", "1e-13", "2" * 100])
def test_produced_invalid(scenario, bad):
    svc, _, _, client, _ = scenario
    with pytest.raises(ValueError):
        close(svc, quantite_produite=bad)
    client.rpc.assert_not_called()


@pytest.mark.parametrize("bad", [-1, None, True, "bad", float("nan"), "1e15", "1e-13"])
def test_packaging_qty_invalid(scenario, bad):
    svc, _, _, client, _ = scenario
    with pytest.raises(ValueError):
        close(svc, emballage_mp_id="MP", emballage_consomme=bad)
    client.rpc.assert_not_called()


@pytest.mark.parametrize("pack_id,pack_qty", [(None, 1), ("SAC", 0), ("", 1), ("SAC", -1),
                                                  (True, 10), ("x" * 201, 2)])
def test_packaging_pair_invalid(scenario, pack_id, pack_qty):
    svc, _, _, client, _ = scenario
    with pytest.raises(ValueError):
        close(svc, emballage_mp_id=pack_id, emballage_consomme=pack_qty)
    client.rpc.assert_not_called()


@pytest.mark.parametrize("qty,pack_id,pack_qty", [(1, None, 0), (0, "SAC", 1), (1, "SAC", 1)])
def test_rejected_forbids_output_and_consumption(scenario, qty, pack_id, pack_qty):
    svc, _, _, client, _ = scenario
    with pytest.raises(ValueError):
        close(svc, conforme="NON", quantite_produite=qty, emballage_mp_id=pack_id, emballage_consomme=pack_qty)
    client.rpc.assert_not_called()


def test_production_permission_fails_closed(scenario):
    svc, db, _, client, _ = scenario
    db.check_server_permission.return_value = False
    with pytest.raises(PermissionError):
        close(svc)
    client.rpc.assert_not_called()


@pytest.mark.parametrize("denied", ["mouvements", "mouvements_pf"])
def test_stock_permission_fails_closed(scenario, denied):
    svc, db, _, client, _ = scenario
    db.check_server_permission.side_effect = lambda t: t != denied
    with pytest.raises(PermissionError):
        close(svc)
    client.rpc.assert_not_called()


def test_rejected_does_not_need_stock_permission(scenario):
    svc, db, _, client, _ = scenario
    db.check_server_permission.side_effect = lambda t: t == "controle_qualite"
    assert close(svc, conforme="NON", quantite_produite=0)["statut"] == "REJETE"


def test_timeout_error_preserves_of_id(scenario):
    svc, _, _, client, _ = scenario
    client.rpc.side_effect = TimeoutError("contains private gateway address")
    with pytest.raises(svc.FabricationOperationError, match="MÊMES paramètres") as exc:
        close(svc)
    assert exc.value.of_id == "OF-001"
    assert "gateway" not in str(exc.value)


@pytest.mark.parametrize("data", [None, [], {}, {"of_id": "OTHER", "statut": "TERMINE"},
                                     {"of_id": "OF-001", "statut": "UNKNOWN"},
                                     {"of_id": "OF-001", "statut": "REJETE"}])
def test_bad_response_fails_closed(scenario, data):
    svc, _, _, client, _ = scenario
    client.rpc.side_effect = lambda *args: types.SimpleNamespace(execute=lambda: types.SimpleNamespace(data=data))
    with pytest.raises(svc.FabricationOperationError):
        close(svc)


def test_response_rejected_if_wrong_status(scenario):
    svc, _, _, client, _ = scenario
    client.rpc.side_effect = lambda *args: types.SimpleNamespace(execute=lambda: types.SimpleNamespace(data={"of_id":"OF-001", "statut":"TERMINE"}))
    with pytest.raises(svc.FabricationOperationError):
        close(svc, conforme="NON", quantite_produite=0)


def test_change_status_does_not_allow_bypassing_cq(scenario):
    svc, db, _, client, _ = scenario
    for status in ("TERMINE", "REJETE", "ABANDONNE", "PLANIFIE", "termine"):
        with pytest.raises(ValueError):
            svc.changer_statut_of("OF-001", status)
    db.update_hybrid.assert_not_called()
    client.rpc.assert_not_called()


def test_change_status_in_progress_is_atomic(scenario):
    svc, db, _, client, _ = scenario
    client.rpc.side_effect = lambda name, params: types.SimpleNamespace(
        execute=lambda: types.SimpleNamespace(data={"of_id": params["p_of_id"], "statut": "EN_COURS"}))
    ret = svc.changer_statut_of("OF-001", "EN_COURS")
    assert ret == {"of_id": "OF-001", "statut": "EN_COURS"}
    assert client.rpc.call_args.args[0] == "erp_start_manufacturing_order"
    db.update_hybrid.assert_not_called()
    db.check_server_permission.assert_called_once_with("ordres_fabrication")


def test_change_status_permission_denied(scenario):
    svc, db, _, client, _ = scenario
    db.check_server_permission.return_value = False
    with pytest.raises(PermissionError):
        svc.changer_statut_of("OF-001", "EN_COURS")
    client.rpc.assert_not_called()


def test_change_status_network_failure(scenario):
    svc, _, _, client, _ = scenario
    client.rpc.side_effect = ConnectionError("private")
    with pytest.raises(svc.FabricationOperationError) as exc:
        svc.changer_statut_of("OF-001", "EN_COURS")
    assert exc.value.of_id == "OF-001"
    assert "private" not in str(exc.value)


def test_change_status_unexpected_response(scenario):
    svc, _, _, client, _ = scenario
    client.rpc.side_effect = lambda *args: types.SimpleNamespace(
        execute=lambda: types.SimpleNamespace(data={"of_id":"OF-001", "statut":"TERMINE"}))
    with pytest.raises(svc.FabricationOperationError):
        svc.changer_statut_of("OF-001", "EN_COURS")


@pytest.mark.parametrize("method,table,column,value", [
    ("get_lignes_recette", "lignes_recette", "recette_id", "REC-1"),
    ("get_consommations_of", "consommations_of", "of_id", "OF-1"),
    ("get_controles_qualite", "controle_qualite", "of_id", "OF-1"),
])
def test_filtered_fetch_is_server_side(scenario, method, table, column, value):
    svc, db, _, _, _ = scenario
    db.fetch_data_filtered.return_value = [{column: value}]
    result = getattr(svc, method)(value)
    assert len(result) == 1
    db.fetch_data_filtered.assert_called_once_with(table, column, value)
    db.fetch_data.assert_not_called()


def test_create_recipe_one_atomic_rpc(scenario):
    svc, db, _, client, util = scenario
    util.get_local_now.return_value = types.SimpleNamespace(strftime=lambda fmt: "2026-10-20")
    result = svc.create_recette("PF", "V1", 1000, "", [
        {"mp_id": "MP", "quantite_par_unite": 0.3}], operation_id="REC-OP-001")
    assert result == "REC-0001"
    name, params = client.rpc.call_args.args
    assert name == "erp_create_recipe"
    assert params["p_lignes"] == [{"mp_id": "MP", "quantite_par_unite": "0.3"}]
    assert params["p_date_effet"] == "2026-10-20"
    assert params["p_operation_id"] == "REC-OP-001"
    db.check_server_permission.assert_any_call("recettes")
    db.check_server_permission.assert_any_call("lignes_recette")
    db.insert_hybrid.assert_not_called()


def test_create_of_one_atomic_rpc(scenario):
    svc, db, _, client, _ = scenario
    out = svc.create_ordre_fabrication("PF", "REC", "SKU", 500, "2026-10-20", "",
                                       operation_id="OF-OP-001")
    assert out == "OF-0001"
    name, params = client.rpc.call_args.args
    assert name == "erp_create_manufacturing_order"
    assert params["p_quantite_prevue"] == "500"
    assert params["p_operation_id"] == "OF-OP-001"
    db.check_server_permission.assert_called_once_with("ordres_fabrication")
    db.insert_hybrid.assert_not_called()


def test_create_recipe_no_permission_refuses_rpc(scenario):
    svc, db, _, client, util = scenario
    util.get_local_now.return_value = types.SimpleNamespace(strftime=lambda fmt: "2026-10-20")
    db.check_server_permission.side_effect = lambda table: table != "lignes_recette"
    with pytest.raises(PermissionError):
        svc.create_recette("PF", "V1", 100, "", [{"mp_id": "MP", "quantite_par_unite": 1}])
    client.rpc.assert_not_called()


def test_create_of_no_permission_refuses_rpc(scenario):
    svc, db, _, client, _ = scenario
    db.check_server_permission.return_value = False
    with pytest.raises(PermissionError):
        svc.create_ordre_fabrication("PF", "REC", "SKU", 10, "2026-10-20", "")
    client.rpc.assert_not_called()


def test_create_of_timeout_operation_id_recoverable(scenario):
    svc, _, _, client, _ = scenario
    client.rpc.side_effect = TimeoutError("secret endpoint address")
    with pytest.raises(svc.ProductionCreationError) as exc:
        svc.create_ordre_fabrication("PF", "REC", "SKU", 10, "2026-10-20", "",
                                     operation_id="ID-STABLE-1")
    assert exc.value.operation_id == "ID-STABLE-1"
    assert "secret endpoint" not in str(exc.value)


def test_create_recipe_timeout_operation_id_recoverable(scenario):
    svc, _, _, client, util = scenario
    util.get_local_now.return_value = types.SimpleNamespace(strftime=lambda fmt: "2026-10-20")
    client.rpc.side_effect = TimeoutError("secret endpoint address")
    with pytest.raises(svc.ProductionCreationError) as exc:
        svc.create_recette("PF", "V1", 100, "", [{"mp_id": "MP", "quantite_par_unite": 1}],
                           operation_id="ID-STABLE-2")
    assert exc.value.operation_id == "ID-STABLE-2"


@pytest.mark.parametrize("data", [None, {}, [], {"of_id": "OF-1"},
                                  {"operation_id": "BAD", "of_id": "OF-1"},
                                  {"operation_id": "FIXED", "of_id": ""}])
def test_create_of_unverified_rpc_response(scenario, data):
    svc, _, _, client, _ = scenario
    client.rpc.side_effect = lambda name, params: types.SimpleNamespace(
        execute=lambda: types.SimpleNamespace(data=data))
    with pytest.raises(svc.ProductionCreationError):
        svc.create_ordre_fabrication("PF", "REC", "SKU", 10, "2026-10-20", "",
                                     operation_id="FIXED")


@pytest.mark.parametrize("rows", [[], None, {}, [{"mp_id": "MP"}],
     [{"mp_id": "MP", "quantite_par_unite": 0}],
     [{"mp_id": "MP", "quantite_par_unite": float("nan")}],
     [{"mp_id": "MP", "quantite_par_unite": 1},
      {"mp_id": "MP", "quantite_par_unite": 2}]])
def test_invalid_recipes_do_not_call_rpc(scenario, rows):
    svc, _, _, client, _ = scenario
    with pytest.raises(ValueError):
        svc.create_recette("PF", "V1", 100, "", rows)
    client.rpc.assert_not_called()


@pytest.mark.parametrize("qty", [0, -1, 1.5, "NaN", float("inf"), True, None])
def test_invalid_of_quantity_do_not_call_rpc(scenario, qty):
    svc, _, _, client, _ = scenario
    with pytest.raises(ValueError):
        svc.create_ordre_fabrication("PF", "REC", "SKU", qty, "2026-10-20", "")
    client.rpc.assert_not_called()


def test_invalid_creation_date_rejected(scenario):
    svc, _, _, client, _ = scenario
    with pytest.raises(ValueError):
        svc.create_ordre_fabrication("PF", "REC", "SKU", 10, "2026-02-30", "")
    client.rpc.assert_not_called()


def test_recipe_explicit_date_kept_for_retry(scenario):
    svc, _, _, client, util = scenario
    svc.create_recette("PF", "V1", 100, "", [{"mp_id": "MP", "quantite_par_unite": 1}],
                       operation_id="RETRY-1", date_effet="2026-10-21")
    assert client.rpc.call_args.args[1]["p_date_effet"] == "2026-10-21"
    util.get_local_now.assert_not_called()


def test_sql_008_contract_static():
    sql = (BASE / "sql" / "008_atomic_production_creation.sql").read_text(encoding="utf-8")
    for fragment in ("public.erp_create_recipe", "public.erp_create_manufacturing_order",
                     "public.erp_production_creations", "pg_advisory_xact_lock",
                     "public.lignes_recette", "public.ordres_fabrication", "SECURITY INVOKER",
                     "ENABLE ROW LEVEL SECURITY", "REVOKE ALL ON FUNCTION",
                     "TO service_role", "COMMIT;"):
        assert fragment in sql
    assert "DELETE FROM" not in sql.upper()


def test_sql_contract_static():
    sql = SQL.read_text(encoding="utf-8")
    for token in (
        "public.erp_close_manufacturing_order", "public.erp_apply_stock_movement",
        "public.erp_of_closures", "public.erp_of_outbox",
        "public.erp_start_manufacturing_order",
        "public.consommations_of", "lot_allocations",
        "public.controle_qualite", "public.ordres_fabrication",
        "public.recettes", "public.lignes_recette", "public.stock_actuel_pf",
    ):
        if token == "public.stock_actuel_pf":
            continue  # entry PF is delegated to atomic stock function
        assert token in sql
    assert "REVOKE ALL ON FUNCTION" in sql
    assert "GRANT EXECUTE ON FUNCTION" in sql
    assert "TO service_role" in sql
    assert "COMMIT;" in sql
    assert "SECURITY INVOKER" in sql
    assert "FOR UPDATE" in sql
    assert "ORDER BY mp_id" in sql


def test_source_does_not_make_individual_stock_calls(scenario):
    source = SCRIPT.read_text(encoding="utf-8")
    assert "enregistrer_sortie_mp(" not in source
    assert "enregistrer_entree_pf(" not in source
    assert '"FIFO-"' not in source
    assert '"EMB-"' not in source
