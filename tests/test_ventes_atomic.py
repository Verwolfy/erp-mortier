"""Contrats Python Ventes (faux backend) ; n'écrit dans aucune base réelle."""
from __future__ import annotations

import importlib.util
import sys
import types
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'modules' / 'ventes' / 'service.py'
SQL = ROOT / 'sql' / '005_atomic_sales.sql'


@pytest.fixture
def sales(monkeypatch):
    db = types.ModuleType('core.db_service')
    db.check_server_permission = Mock(return_value=True)
    db.fetch_data = Mock(return_value=[])
    db.fetch_data_filtered = Mock(return_value=[])
    db.get_supabase_client = Mock()
    utils = types.ModuleType('core.utils')
    utils.get_local_now = Mock()
    stock = types.ModuleType('modules.stocks.service')
    stock._stock_rpc_client = Mock()
    client = stock._stock_rpc_client.return_value

    def rpc(name, params):
        assert name == 'erp_sale_transaction'
        action = params['p_action']
        key = 'bl_id' if action == 'SHIP' else 'facture_id'
        result = {'operation_id': params['p_operation_id'], 'action': action,
                  key: 'BL-AAA' if action == 'SHIP' else 'FAC-2026-000001'}
        return types.SimpleNamespace(execute=lambda: types.SimpleNamespace(data=result))
    client.rpc.side_effect = rpc
    modules = [
        ('core', types.ModuleType('core')),
        ('core.db_service', db),
        ('core.utils', utils),
        ('modules', types.ModuleType('modules')),
        ('modules.stocks', types.ModuleType('modules.stocks')),
        ('modules.stocks.service', stock),
    ]
    for name, module in modules:
        monkeypatch.setitem(sys.modules, name, module)
    spec = importlib.util.spec_from_file_location('local_ventes', SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, db, client


def panier():
    return [{'sku_id': 'SKU-1', 'quantite': '2', 'prix_unitaire': '100', 'remise': '5'}]


def facture(mod, **kwargs):
    args = dict(client_id='CL-1', date_echeance='2026-11-30', panier=panier(),
                remise_globale='10', paiement_especes=False)
    args.update(kwargs)
    return mod.create_facture_brouillon(**args)


def test_invoice_rpc_single_transaction_no_stock(sales):
    mod, db, client = sales
    assert facture(mod, operation_id='BILL-ID') == 'FAC-2026-000001'
    action, params = client.rpc.call_args.args
    assert action == 'erp_sale_transaction'
    assert params['p_action'] == 'DRAFT'
    assert params['p_operation_id'] == 'BILL-ID'
    assert params['p_payload']['montant_ht'] == '185.00'
    assert params['p_payload']['lignes'][0]['total_ligne_ht'] == '195.00'
    assert params['p_payload']['montant_tva'] == '35.15'
    assert params['p_payload']['montant_ttc'] == '220.15'
    db.check_server_permission.assert_called_once_with('factures')


def test_credit_note_negative_and_requires_origin(sales):
    mod, _, client = sales
    assert facture(mod, is_avoir=True, facture_origine_id='FAC-OLD',
                   operation_id='CREDIT') == 'FAC-2026-000001'
    payload = client.rpc.call_args.args[1]['p_payload']
    assert payload['montant_ht'] == '-185.00'
    assert payload['montant_tva'] == '-35.15'
    assert payload['montant_ttc'] == '-220.15'
    assert payload['montant_timbre'] == '0'
    assert payload['facture_origine_id'] == 'FAC-OLD'


def test_validation_no_stock(sales):
    mod, db, client = sales
    mod.valider_facture('FAC-100', operation_id='VALIDATION')
    assert client.rpc.call_args.args[1]['p_action'] == 'VALIDATE'
    assert client.rpc.call_args.args[1]['p_payload'] == {'facture_id': 'FAC-100'}
    db.check_server_permission.assert_called_once_with('factures')


def test_cancel_never_restocks(sales):
    mod, _, client = sales
    mod.annuler_facture('FAC-100', operation_id='CANCEL')
    assert client.rpc.call_args.args[1]['p_action'] == 'CANCEL'
    assert client.rpc.call_args.args[1]['p_payload'] == {'facture_id': 'FAC-100'}


def test_shipment_with_fifo_and_stocks_permission(sales):
    mod, db, client = sales
    assert mod.creer_bon_livraison('CMD-1', 'T', 'Nord',
        [{'sku_id': 'SKU-1', 'quantite_livree': '2.5', 'lot_id': 'DEFAUT'}],
        operation_id='SHIP-1') == 'BL-AAA'
    payload = client.rpc.call_args.args[1]
    assert payload['p_action'] == 'SHIP'
    assert payload['p_payload']['lignes'][0] == {'sku_id': 'SKU-1', 'quantite_livree': '2.5'}
    assert [x.args for x in db.check_server_permission.call_args_list] == [('bons_livraison',), ('mouvements_pf',)]


def test_no_partial_client_side_writes(sales):
    mod, _, client = sales
    assert 'enregistrer_sortie_pf' not in mod.__dict__
    assert 'enregistrer_entree_pf' not in mod.__dict__
    assert 'insert_hybrid' not in mod.__dict__
    assert 'update_hybrid' not in mod.__dict__
    assert callable(client.rpc)


def test_legacy_number_does_not_update_counter_twice(sales):
    mod, db, _ = sales
    db.fetch_data_filtered.return_value = [{'prefixe':'FAC','annee':'2026','dernier_numero':10}]
    db.get_supabase_client.return_value.rpc.return_value.execute.return_value.data = 11
    assert mod.generer_numero_facture_legal('FactureClient') == 'FAC-2026-000011'
    db.get_supabase_client.return_value.rpc.assert_called_once_with('increment_compteur', {'p_type_document':'FactureClient'})


def test_legacy_number_invalid_server_response(sales):
    mod, db, _ = sales
    db.fetch_data_filtered.return_value = [{'prefixe':'F','annee':'2026'}]
    db.get_supabase_client.return_value.rpc.return_value.execute.return_value.data = 'invalid'
    with pytest.raises(RuntimeError):
        mod.generer_numero_facture_legal('FactureClient')


@pytest.mark.parametrize('value', [0,-1,'-0.01','NaN','Infinity','-Infinity',True,None,'abc','1e20','1e-25'])
def test_bad_invoice_quantity(sales,value):
    mod, _, client = sales
    p = panier(); p[0]['quantite'] = value
    with pytest.raises(ValueError): facture(mod,panier=p)
    client.rpc.assert_not_called()


@pytest.mark.parametrize('key,value',[
    ('prix_unitaire', -1), ('prix_unitaire','NaN'), ('prix_unitaire', True),
    ('remise', -1),('remise','Infinity'),('remise',True),('remise',1000),
    ('sku_id', ''), ('sku_id', None), ('sku_id', 'x'*201)
])
def test_bad_invoice_line(sales,key,value):
    mod, _, client = sales
    p = panier(); p[0][key] = value
    with pytest.raises(ValueError): facture(mod,panier=p)
    client.rpc.assert_not_called()


@pytest.mark.parametrize('v',[[],{},None,[None],['not dictionary'],[{}],panier()*501])
def test_bad_invoice_cart(sales,v):
    mod, _, client = sales
    with pytest.raises(ValueError): facture(mod,panier=v)
    client.rpc.assert_not_called()


@pytest.mark.parametrize('v',[-1,'NaN','Infinity','99999',True,None])
def test_bad_global_discount(sales,v):
    mod,_,client=sales
    with pytest.raises(ValueError): facture(mod,remise_globale=v)
    client.rpc.assert_not_called()


def test_line_discounts_are_amounts_not_percent(sales):
    mod,_,_=sales
    result=mod.calculer_montants_facture(panier(),remise_globale=10)
    assert result['net_a_payer'] == 185.0
    assert result['total_remise'] == 15.0
    assert result['total_tva'] == 35.15


def test_cash_stamp_and_cap(sales):
    mod,_,_=sales
    r=mod.calculer_montants_facture(panier(),remise_globale=10,paiement_especes=True)
    assert r['timbre_fiscal'] == 2.2
    assert r['total_ttc'] == 222.35
    r2=mod.calculer_montants_facture([{'sku_id':'SK','quantite':1,'prix_unitaire':1_000_000}],paiement_especes=True)
    assert r2['timbre_fiscal']==2500


def test_rounded_line_and_cents_words(sales):
    mod,_,_=sales
    v=mod.calculer_montants_facture([{'sku_id':'SK','quantite':3,'prix_unitaire':'0.335'}])
    assert v['net_a_payer']==1.01
    assert v['total_ttc']==1.20


def test_avoir_does_not_accept_cash_or_missing_origin(sales):
    mod,_,client=sales
    with pytest.raises(ValueError): facture(mod,is_avoir=True)
    with pytest.raises(ValueError): facture(mod,is_avoir=True,facture_origine_id='FAC',paiement_especes=True)
    client.rpc.assert_not_called()


def test_normal_invoice_cannot_reference_origin(sales):
    mod,_,client=sales
    with pytest.raises(ValueError): facture(mod, facture_origine_id='FAC')
    client.rpc.assert_not_called()


@pytest.mark.parametrize('date_str',['2026-02-30','2026-13-02','25/10/2026','2026-1-1',None])
def test_bad_due_date(sales,date_str):
    mod,_,client=sales
    with pytest.raises(ValueError): facture(mod,date_echeance=date_str)
    client.rpc.assert_not_called()


@pytest.mark.parametrize('item',[
    {'sku_id':'SKU','quantite_livree':0},
    {'sku_id':'SKU','quantite_livree':-1},
    {'sku_id':'SKU','quantite_livree':'NaN'},
    {'sku_id':'SKU','quantite_livree':True},
    {'sku_id':'','quantite_livree':5},
    {'sku_id':'SKU','quantite_livree':1,'lot_id':'MANUAL-LOT'}
])
def test_bad_shipment_line(sales,item):
    mod,_,client=sales
    with pytest.raises(ValueError): mod.creer_bon_livraison('CMD','T','N',[item])
    client.rpc.assert_not_called()


def test_denied_permission_no_rpc(sales):
    mod,db,client=sales
    db.check_server_permission.return_value=False
    with pytest.raises(PermissionError): facture(mod)
    with pytest.raises(PermissionError): mod.creer_bon_livraison('CMD','T','N',[{'sku_id':'SKU','quantite_livree':2}])
    client.rpc.assert_not_called()


def test_denied_stock_permission_no_rpc(sales):
    mod,db,client=sales
    db.check_server_permission.side_effect=[True,False]
    with pytest.raises(PermissionError): mod.creer_bon_livraison('CMD','T','N',[{'sku_id':'SKU','quantite_livree':2}])
    client.rpc.assert_not_called()


def test_network_error_exposes_same_operation_id(sales):
    mod,_,client=sales
    client.rpc.side_effect=TimeoutError('Lost reply')
    with pytest.raises(mod.SaleOperationError) as exc:
        facture(mod,operation_id='RETRY-ME')
    assert exc.value.operation_id=='RETRY-ME'


def test_wrong_response_preserves_operation_id(sales):
    mod,_,client=sales
    client.rpc.return_value.execute.return_value.data={'operation_id':'WRONG','action':'DRAFT'}
    client.rpc.side_effect=None
    with pytest.raises(mod.SaleOperationError) as exc:
        facture(mod,operation_id='SAME-ID')
    assert exc.value.operation_id=='SAME-ID'


def test_operation_id_check(sales):
    mod,_,client=sales
    with pytest.raises(ValueError): facture(mod,operation_id=' ')
    with pytest.raises(ValueError): facture(mod,operation_id='x'*129)
    client.rpc.assert_not_called()


def test_sql_contract(sales):
    text=SQL.read_text(encoding='utf-8')
    assert 'CREATE OR REPLACE FUNCTION public.erp_sale_transaction' in text
    assert 'FOR UPDATE' in text
    assert 'erp_apply_stock_movement' in text
    assert "'lot_allocations'" in text
    assert 'GRANT EXECUTE ON FUNCTION public.erp_sale_transaction(text,text,jsonb) TO service_role' in text
    assert "FROM PUBLIC, anon, authenticated" in text
    assert 'public.erp_sales_outbox' in text
    assert 'p_operation_id' in text
    assert 'Seuls les brouillons peuvent être validés ou annulés' in text
    assert 'Aucune entrée en stock' in text
