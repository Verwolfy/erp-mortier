"""Tests hors réseau des contrats Python Achats et garde-fous de la migration."""
from __future__ import annotations

import importlib.util
import sys
import types
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "modules" / "achats" / "service.py"
SQL = ROOT / "sql" / "004_atomic_purchases.sql"


@pytest.fixture
def achats(monkeypatch):
    db = types.ModuleType("core.db_service")
    db.check_server_permission = Mock(return_value=True)
    db.fetch_data = Mock(side_effect=lambda table: [])
    db.fetch_data_filtered = Mock(side_effect=lambda t, c, v: [{c: v}])
    db.insert_hybrid = Mock()
    db.update_hybrid = Mock()
    utils = types.ModuleType("core.utils")
    utils.generate_unique_id = Mock(side_effect=lambda prefix, ids: f"{prefix}-0001")
    utils.generate_technical_id = Mock(side_effect=lambda prefix: f"{prefix}-XYZ")
    utils.get_local_now = Mock()
    stock = types.ModuleType("modules.stocks.service")
    stock._stock_rpc_client = Mock()
    client = stock._stock_rpc_client.return_value
    def rpc(name, params):
        assert name in ("erp_create_purchase_order", "erp_receive_purchase_order")
        doc_field = "commande_achat_id" if name == "erp_create_purchase_order" else "bon_reception_id"
        doc_value = params["p_order_id" if name == "erp_create_purchase_order" else "p_br_id"]
        return types.SimpleNamespace(execute=lambda: types.SimpleNamespace(data={
            "operation_id": params["p_operation_id"], doc_field: doc_value,
        }))
    client.rpc.side_effect = rpc
    for name, obj in [("core", types.ModuleType("core")),
                      ("core.db_service", db), ("core.utils", utils),
                      ("modules", types.ModuleType("modules")),
                      ("modules.stocks", types.ModuleType("modules.stocks")),
                      ("modules.stocks.service", stock)]:
        monkeypatch.setitem(sys.modules, name, obj)
    spec = importlib.util.spec_from_file_location("test_achat_module", SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, db, utils, client


def cmd(mod, **kw):
    args = dict(fournisseur_id="FOU-1", type_achat="MP", devise="EUR", taux_change="130",
                mode_paiement="Virement", delai_paiement="30J", date_voulue="2026-10-27",
                panier=[{"mp_id":"MP-1","unite_cond":"KG","qte_cond":50,
                         "qte_totale":50,"prix_unitaire":4,"total_devise":200}])
    args.update(kw)
    return mod.create_commande_achat(**args)


def receipt(mod, **kw):
    args = dict(commande_achat_id="CMA-0001",date_reception="2026-10-26",
                controle_conformite="OUI",remarques="Conforme",
                items_recus=[{"mp_id":"MP-1","quantite_recue":"20","prix_unitaire":"4.25"}],
                date_peremption="2027-10-26")
    args.update(kw)
    return mod.creer_bon_reception(**args)


def test_order_single_atomic_rpc(achats):
    mod, db, _, client = achats
    assert cmd(mod, operation_id="OP-ORDER") == "CMA-0001"
    client.rpc.assert_called_once()
    name, payload = client.rpc.call_args.args
    assert name == "erp_create_purchase_order"
    assert payload["p_lines"][0]["qte_totale"] == "50"
    assert payload["p_taux_change"] == "130"
    assert payload["p_operation_id"] == "OP-ORDER"
    db.insert_hybrid.assert_not_called()
    db.update_hybrid.assert_not_called()
    db.check_server_permission.assert_called_once_with("commandes_achats")


def test_receipt_single_atomic_rpc(achats):
    mod, db, _, client = achats
    assert receipt(mod,operation_id="OP-RECEPTION") == "BR-0001"
    name, payload = client.rpc.call_args.args
    assert name == "erp_receive_purchase_order"
    assert payload["p_lines"][0]["quantite_recue"] == "20"
    assert payload["p_date_peremption"] == "2027-10-26"
    assert payload["p_operation_id"] == "OP-RECEPTION"
    db.check_server_permission.assert_any_call("bons_reception")
    db.check_server_permission.assert_any_call("mouvements")
    db.insert_hybrid.assert_not_called()
    db.update_hybrid.assert_not_called()


@pytest.mark.parametrize("value",["NaN","Infinity","-Infinity",float("inf"),float("-inf"),
                                  -1,0,True,None,"no", "1e100"])
def test_bad_order_exchange_rate(achats,value):
    mod,_,_,client=achats
    with pytest.raises(ValueError): cmd(mod,taux_change=value)
    client.rpc.assert_not_called()


@pytest.mark.parametrize("field,value",[
    ("qte_cond",0),("qte_cond",-1),("qte_cond","NaN"),("qte_totale",0),
    ("qte_totale",-10),("qte_totale","Infinity"),("prix_unitaire",-1),
    ("prix_unitaire",None),("prix_unitaire",True),("total_devise",-1),
    ("total_devise","NaN"),("mp_id",None),("mp_id",""),
    ("unite_cond",None),
])
def test_bad_order_line(achats,field,value):
    mod,_,_,client=achats
    line=dict(mp_id="MP",unite_cond="KG",qte_cond=25,qte_totale=25,prix_unitaire=3,total_devise=75)
    line[field]=value
    with pytest.raises(ValueError): cmd(mod,panier=[line])
    client.rpc.assert_not_called()


@pytest.mark.parametrize("value",[[],{},None,[None], ["abc"]])
def test_bad_order_lines(achats,value):
    mod,_,_,client=achats
    with pytest.raises(ValueError): cmd(mod,panier=value)
    client.rpc.assert_not_called()


@pytest.mark.parametrize("value",[-1,0,"NaN",float("inf"),None,True,"abc","1e3000"])
def test_bad_receipt_quantity(achats,value):
    mod,_,_,client=achats
    with pytest.raises(ValueError):
        receipt(mod,items_recus=[{"mp_id":"MP-1","quantite_recue":value,"prix_unitaire":1}])
    client.rpc.assert_not_called()


@pytest.mark.parametrize("value",[-1,"Infinity","NaN",None,True,"1e100"])
def test_bad_receipt_cost(achats,value):
    mod,_,_,client=achats
    with pytest.raises(ValueError):
        receipt(mod,items_recus=[{"mp_id":"MP-1","quantite_recue":1,"prix_unitaire":value}])
    client.rpc.assert_not_called()


@pytest.mark.parametrize("value",["NON","conforme","",None])
def test_not_conform_refused(achats,value):
    mod,_,_,client=achats
    with pytest.raises(ValueError): receipt(mod,controle_conformite=value)
    client.rpc.assert_not_called()


@pytest.mark.parametrize("field,value",[("fournisseur_id",""),("fournisseur_id",None),
                                  ("devise",""),("type_achat",""),
                                  ("operation_id",""),("operation_id","X"*129)])
def test_invalid_order_header(achats,field,value):
    mod,_,_,client=achats
    with pytest.raises(ValueError): cmd(mod,**{field:value})
    client.rpc.assert_not_called()


@pytest.mark.parametrize("field,value",[("commande_achat_id",""),("date_reception",""),
                                  ("date_reception",None),( "date_peremption","X"*41),
                                  ("operation_id",""),("operation_id","X"*130)])
def test_invalid_receipt_header(achats,field,value):
    mod,_,_,client=achats
    with pytest.raises(ValueError): receipt(mod,**{field:value})
    client.rpc.assert_not_called()


def test_permission_order_denied(achats):
    mod,db,_,client=achats
    db.check_server_permission.return_value=False
    with pytest.raises(PermissionError): cmd(mod)
    client.rpc.assert_not_called()


def test_permission_receipt_denied_stocks(achats):
    mod,db,_,client=achats
    db.check_server_permission.side_effect=lambda t:t!="mouvements"
    with pytest.raises(PermissionError): receipt(mod)
    client.rpc.assert_not_called()


def test_permission_receipt_denied_achats(achats):
    mod,db,_,client=achats
    db.check_server_permission.side_effect=lambda t:t!="bons_reception"
    with pytest.raises(PermissionError): receipt(mod)
    client.rpc.assert_not_called()


@pytest.mark.parametrize("op",["order","receipt"])
def test_unknown_network_error_preserves_operation_id(achats,op):
    mod,_,_,client=achats
    client.rpc.side_effect=RuntimeError("secret internal failure")
    with pytest.raises(mod.PurchaseOperationError,match="MÊME operation_id") as caught:
        (cmd(mod,operation_id="RESUME-1") if op=="order"
         else receipt(mod,operation_id="RESUME-1"))
    assert caught.value.operation_id=="RESUME-1"
    assert "secret internal" not in str(caught.value)


@pytest.mark.parametrize("op",["order","receipt"])
def test_bad_rpc_response_rejected(achats,op):
    mod,_,_,client=achats
    client.rpc.side_effect=lambda name, params: types.SimpleNamespace(
        execute=lambda:types.SimpleNamespace(data={"operation_id":params["p_operation_id"]}))
    with pytest.raises(mod.PurchaseOperationError) as caught:
        (cmd(mod, operation_id="ABC") if op=="order" else receipt(mod,operation_id="ABC"))
    assert caught.value.operation_id=="ABC"


def test_decimal_precision(achats):
    mod,_,_,client=achats
    cmd(mod,taux_change=Decimal("1.00003"),panier=[{
        "mp_id":"MP","unite_cond":"KG","qte_cond":Decimal("0.125"),
        "qte_totale":Decimal("0.125"),"prix_unitaire":Decimal("2.375"),
        "total_devise":Decimal("0.296875")
    }])
    payload=client.rpc.call_args.args[1]
    assert payload["p_lines"][0]["qte_totale"]=="0.125"
    assert payload["p_taux_change"]=="1.00003"


def test_get_lines_are_filtered_in_supabase(achats):
    mod,db,_,_=achats
    assert mod.get_lignes_achats("CMA-10").iloc[0]["commande_achat_id"]=="CMA-10"
    db.fetch_data_filtered.assert_called_with("lignes_achats","commande_achat_id","CMA-10")
    assert mod.get_lignes_bons_reception("BR-10").iloc[0]["bon_reception_id"]=="BR-10"
    db.fetch_data_filtered.assert_called_with("lignes_bons_reception","bon_reception_id","BR-10")


def test_unfiltered_read_support(achats):
    mod,db,_,_=achats
    assert mod.get_commandes().empty
    assert mod.get_bons_reception().empty
    assert mod.get_lignes_achats().empty
    assert mod.get_lignes_bons_reception().empty
    assert db.fetch_data.call_count==4


def test_max_lines(achats):
    mod,_,_,client=achats
    panier=[dict(mp_id="MP",unite_cond="SAC",qte_cond=1,qte_totale=1,
                 prix_unitaire=1,total_devise=1)]*501
    with pytest.raises(ValueError): cmd(mod,panier=panier)
    client.rpc.assert_not_called()


def test_sql_transaction_properties_and_replay_contract():
    sql=SQL.read_text(encoding="utf-8")
    assert "public.erp_apply_stock_movement(" in sql
    assert "FOR UPDATE" in sql
    assert "PARTIELLEMENT_RECEPTIONNE" in sql
    assert "lot_attribue_id" in sql
    assert "v_lot->>'lot_id'" in sql
    assert "CREATE TABLE IF NOT EXISTS public.erp_purchase_operations" in sql
    assert "SECURITY INVOKER" in sql
    assert "TO service_role" in sql
    assert "e.item - 'ligne_br_id'" in sql
    assert "e.item - 'ligne_achat_id'" in sql


def test_no_direct_stock_writes_in_python():
    import ast
    tree=ast.parse(SRC.read_text(encoding="utf-8"))
    calls=[node.func.id for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Name)]
    assert "insert_hybrid" not in calls
    assert "update_hybrid" not in calls
    assert "enregistrer_entree_mp" not in calls


def test_existing_signature_is_compatible(achats):
    import inspect
    mod,_,_,_=achats
    signature=inspect.signature(mod.creer_bon_reception)
    assert list(signature.parameters)[:6]==["commande_achat_id","date_reception",
           "controle_conformite","remarques","items_recus","date_peremption"]
    assert signature.parameters["operation_id"].kind==inspect.Parameter.KEYWORD_ONLY


def test_unconfigured_pack_conversion_remains_forbidden(achats):
    mod, _, _, client = achats
    with pytest.raises(ValueError, match="conditionnement"):
        cmd(mod, panier=[{
            "mp_id": "MP-1", "unite_cond": "SAC",
            "qte_cond": 2, "qte_totale": 50,
            "prix_unitaire": 4, "total_devise": 200,
        }])
    client.rpc.assert_not_called()
