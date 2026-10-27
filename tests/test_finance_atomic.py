"""Tests unitaires Finance avec RPC simulée : aucune connexion à Supabase."""
from __future__ import annotations

import importlib.util
import sys
import types
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / 'sql' / '006_atomic_finance.sql'
SOURCE = ROOT / 'modules' / 'finance' / 'service.py'


@pytest.fixture
def finance(monkeypatch):
    db = types.ModuleType('core.db_service')
    db.check_server_permission = Mock(return_value=True)
    db.fetch_data = Mock(return_value=[])
    stock = types.ModuleType('modules.stocks.service')
    stock._stock_rpc_client = Mock()
    client = stock._stock_rpc_client.return_value

    def rpc(name, params):
        assert name == 'erp_finance_transaction'
        act = params['p_action']
        key = {'ACCOUNT': 'compte_id', 'PAYMENT': 'reglement_id', 'ALLOCATE': 'lettrage_id'}[act]
        return types.SimpleNamespace(execute=lambda: types.SimpleNamespace(
            data={'action': act, 'operation_id': params['p_operation_id'], key: 'ID-1'}))

    client.rpc.side_effect = rpc
    for name, module in [('core', types.ModuleType('core')), ('core.db_service', db),
                         ('modules', types.ModuleType('modules')),
                         ('modules.stocks', types.ModuleType('modules.stocks')),
                         ('modules.stocks.service', stock)]:
        monkeypatch.setitem(sys.modules, name, module)
    spec = importlib.util.spec_from_file_location('local_finance', SOURCE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, db, client


def reglement(mod, **kwargs):
    params = dict(date_reglement='2026-10-20', type_flux='ENCAISSEMENT', partenaire_id='CL1',
                  compte_id='BANK1', mode_paiement='VIREMENT', reference_trace='BANK-REF-001',
                  montant_total='100.25', contrepartie_compte_id='411CL1')
    params.update(kwargs)
    return mod.enregistrer_reglement(**params)


def lettrage(mod, **kwargs):
    params = dict(reglement_id='REG-1', document_id='FAC-001',
                  type_document='FactureClient', montant_applique='75.00')
    params.update(kwargs)
    return mod.enregistrer_lettrage(**params)


def test_finance_account_atomic(finance):
    mod, db, client = finance
    assert mod.creer_compte('Bancaire', 'BANQUE', '512100', '100.00', operation_id='ACC1') == 'ID-1'
    name, params = client.rpc.call_args.args
    assert name == 'erp_finance_transaction'
    assert params == {'p_action': 'ACCOUNT', 'p_operation_id': 'ACC1',
                      'p_payload': {'nom_compte': 'Bancaire', 'type_compte': 'BANQUE',
                                    'numero_compte': '512100', 'solde_initial': '100.00'}}
    db.check_server_permission.assert_called_once_with('comptes')


def test_account_accepts_negative_initial_balance(finance):
    mod, _, client = finance
    mod.creer_compte('Découvert', 'BANQUE', '512', '-12.50')
    assert client.rpc.call_args.args[1]['p_payload']['solde_initial'] == '-12.50'


def test_payment_balanced_rpc(finance):
    mod, db, client = finance
    assert reglement(mod, operation_id='PAY123') == 'ID-1'
    name, params = client.rpc.call_args.args
    assert name == 'erp_finance_transaction'
    assert params['p_action'] == 'PAYMENT'
    assert params['p_operation_id'] == 'PAY123'
    assert params['p_payload']['contrepartie_compte_id'] == '411CL1'
    assert params['p_payload']['montant_total'] == '100.25'
    assert [x.args for x in db.check_server_permission.call_args_list] == [
        ('reglements',), ('ecritures_comptables',)]


def test_payment_explicit_counterpart_required(finance):
    mod, _, client = finance
    with pytest.raises(ValueError, match='contrepartie'):
        reglement(mod, contrepartie_compte_id=None)
    client.rpc.assert_not_called()


def test_payment_accounts_distinct(finance):
    mod, _, client = finance
    with pytest.raises(ValueError):
        reglement(mod, contrepartie_compte_id='BANK1')
    client.rpc.assert_not_called()


def test_allocation_client_rpc(finance):
    mod, db, client = finance
    assert lettrage(mod, operation_id='L1') == 'ID-1'
    params = client.rpc.call_args.args[1]
    assert params['p_action'] == 'ALLOCATE'
    assert params['p_operation_id'] == 'L1'
    assert params['p_payload'] == {'reglement_id': 'REG-1', 'document_id': 'FAC-001',
                                   'type_document': 'FactureClient', 'montant_applique': '75.00'}
    assert [x.args for x in db.check_server_permission.call_args_list] == [
        ('lettrage',), ('reglements',)]


def test_allocation_supplier_rpc(finance):
    mod, _, client = finance
    assert lettrage(mod, type_document='FactureFournisseur') == 'ID-1'
    assert client.rpc.call_args.args[1]['p_payload']['type_document'] == 'FactureFournisseur'


@pytest.mark.parametrize('value', [0, '0.00', -1, '-2.50', 'NaN', 'Infinity', '-Infinity',
                                  None, True, 'abc', '1e20', '1e-20', '1.001', '1000000000000000'])
def test_payment_amount_invalid(finance, value):
    mod, _, client = finance
    with pytest.raises(ValueError):
        reglement(mod, montant_total=value)
    client.rpc.assert_not_called()


@pytest.mark.parametrize('value', [0, -1, 'NaN', None, True, '1.123', '1e20'])
def test_allocation_amount_invalid(finance, value):
    mod, _, client = finance
    with pytest.raises(ValueError):
        lettrage(mod, montant_applique=value)
    client.rpc.assert_not_called()


@pytest.mark.parametrize('value', [None, True, 'NaN', '1e30', '0.001'])
def test_initial_balance_invalid(finance, value):
    mod, _, client = finance
    with pytest.raises(ValueError):
        mod.creer_compte('Banque', 'BANQUE', '512', value)
    client.rpc.assert_not_called()


@pytest.mark.parametrize('value', [None, '2026-02-30', '2026-13-01', '20/10/2026', '2026-1-1'])
def test_date_invalid(finance, value):
    mod, _, client = finance
    with pytest.raises(ValueError):
        reglement(mod, date_reglement=value)
    client.rpc.assert_not_called()


@pytest.mark.parametrize('value', ['', 'AUTRE', None, 'factureclient', 'FactureAvoir'])
def test_allocation_type_invalid(finance, value):
    mod, _, client = finance
    with pytest.raises(ValueError):
        lettrage(mod, type_document=value)
    client.rpc.assert_not_called()


@pytest.mark.parametrize('value', ['', None, 'SORTIE', 'ENCAISSEMENT2'])
def test_direction_invalid(finance, value):
    mod, _, client = finance
    with pytest.raises(ValueError):
        reglement(mod, type_flux=value)
    client.rpc.assert_not_called()


@pytest.mark.parametrize('field,value', [
    ('partenaire_id', ''), ('partenaire_id', None), ('partenaire_id', 'Z'*201),
    ('compte_id', ''), ('compte_id', 'K'*201),
    ('contrepartie_compte_id', ''), ('contrepartie_compte_id', 'Q'*201),
    ('mode_paiement', ''), ('mode_paiement', 'M'*201),
    ('reference_trace', ''), ('reference_trace', None),
])
def test_payment_fields_invalid(finance, field, value):
    mod, _, client = finance
    with pytest.raises(ValueError):
        reglement(mod, **{field: value})
    client.rpc.assert_not_called()


@pytest.mark.parametrize('field,value', [
    ('reglement_id', ''), ('reglement_id', None), ('document_id', ''),
    ('document_id', 'X'*201), ('type_document', 'FactureAvoir'),
])
def test_allocation_fields_invalid(finance, field, value):
    mod, _, client = finance
    with pytest.raises(ValueError):
        lettrage(mod, **{field: value})
    client.rpc.assert_not_called()


@pytest.mark.parametrize('field,value', [
    ('nom_compte', None), ('nom_compte', ''), ('type_compte', ''), ('numero_compte', ''),
    ('numero_compte', 'N'*201),
])
def test_account_fields_invalid(finance, field, value):
    mod, _, client = finance
    args = {'nom_compte': 'Banque', 'type_compte': 'BANQUE', 'numero_compte': '512',
            'solde_initial': 0}
    args[field] = value
    with pytest.raises(ValueError):
        mod.creer_compte(**args)
    client.rpc.assert_not_called()


def test_deny_account_finance_permission(finance):
    mod, db, client = finance
    db.check_server_permission.return_value = False
    with pytest.raises(PermissionError):
        mod.creer_compte('Banque', 'BANQUE', '512', 0)
    client.rpc.assert_not_called()


def test_deny_payment_journal_permission(finance):
    mod, db, client = finance
    db.check_server_permission.side_effect = [True, False]
    with pytest.raises(PermissionError):
        reglement(mod)
    client.rpc.assert_not_called()


def test_deny_allocation_permission(finance):
    mod, db, client = finance
    db.check_server_permission.side_effect = [True, False]
    with pytest.raises(PermissionError):
        lettrage(mod)
    client.rpc.assert_not_called()


def test_timeout_exposes_same_operation_id(finance):
    mod, _, client = finance
    client.rpc.side_effect = TimeoutError('Network timeout')
    with pytest.raises(mod.FinanceOperationError) as e:
        reglement(mod, operation_id='RETRY-SAME')
    assert e.value.operation_id == 'RETRY-SAME'


def test_bad_rpc_result_preserves_operation_id(finance):
    mod, _, client = finance
    client.rpc.side_effect = lambda name, payload: types.SimpleNamespace(
        execute=lambda: types.SimpleNamespace(data={}))
    with pytest.raises(mod.FinanceOperationError) as e:
        lettrage(mod, operation_id='RETRY-L')
    assert e.value.operation_id == 'RETRY-L'


@pytest.mark.parametrize('value', ['', ' ', 'x'*129, 3, None])
def test_invalid_operation_id(finance, value):
    mod, _, client = finance
    with pytest.raises(ValueError):
        reglement(mod, operation_id=value if value is not None else '')
    client.rpc.assert_not_called()


def test_default_operation_id_generated(finance):
    mod, _, client = finance
    reglement(mod)
    assert client.rpc.call_args.args[1]['p_operation_id'].startswith('FIN-')


def test_read_queries(finance):
    mod, db, _ = finance
    mod.get_comptes(); mod.get_reglements(); mod.get_lettrages(); mod.get_ecritures_comptables()
    assert [call.args for call in db.fetch_data.call_args_list] == [
        ('comptes',), ('reglements',), ('lettrage',), ('ecritures_comptables',)]


def test_no_unprotected_multistep_writes(finance):
    mod, _, _ = finance
    assert 'insert_hybrid' not in mod.__dict__
    assert 'update_hybrid' not in mod.__dict__


def test_sql_atomicity_contract():
    sql = SQL.read_text('utf-8')
    assert 'CREATE OR REPLACE FUNCTION public.erp_finance_transaction' in sql
    assert 'SECURITY INVOKER' in sql
    assert 'FOR UPDATE' in sql
    assert 'ON CONFLICT(operation_id) DO NOTHING' in sql
    assert "p_action='ALLOCATE'" in sql
    assert 'sum(montant_applique)' in sql
    assert "v_invoice.type_facture IS DISTINCT FROM 'FactureClient'" in sql
    assert "v_invoice.statut IS DISTINCT FROM 'VALIDE'" in sql
    assert 'UPDATE public.factures SET montant_paye' in sql
    assert "SET statut_paiement=CASE" in sql
    assert 'GRANT EXECUTE ON FUNCTION public.erp_finance_transaction(text,text,jsonb) TO service_role' in sql
    assert 'Référence de règlement déjà enregistrée' in sql
    assert 'pg_advisory_xact_lock' in sql


def test_sql_double_entry_cash_and_counterpart():
    sql = SQL.read_text('utf-8')
    assert sql.count('INSERT INTO public.ecritures_comptables') == 2
    assert "CASE WHEN v_direction='ENCAISSEMENT' THEN v_amount ELSE 0 END" in sql
    assert "CASE WHEN v_direction='DECAISSEMENT' THEN v_amount ELSE 0 END" in sql
    assert "CASE WHEN v_direction='DECAISSEMENT' THEN v_amount ELSE 0 END" in sql
    assert "CASE WHEN v_direction='ENCAISSEMENT' THEN v_amount ELSE 0 END" in sql


def test_sql_no_commercial_status_rewrite():
    sql = SQL.read_text('utf-8')
    assert 'UPDATE public.factures SET statut=' not in sql
    assert "type_document='FactureClient'" not in sql  # proper variable branching used


def test_readonly_preflight_present():
    sql = (ROOT / 'sql' / 'finance_preflight_readonly.sql').read_text('utf-8')
    assert 'information_schema' in sql
    assert 'SELECT' in sql
    assert 'UPDATE ' not in sql.upper()
    assert 'DELETE ' not in sql.upper()
