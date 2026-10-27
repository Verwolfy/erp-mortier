"""Finance 006 : contrats de sûreté statiques et validation client avant RPC."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import sys
import types
from unittest.mock import Mock
import pytest

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture
def finance(monkeypatch):
    db = types.ModuleType('core.db_service')
    db.check_server_permission = Mock(return_value=True)
    db.fetch_data = Mock(return_value=[])
    stock = types.ModuleType('modules.stocks.service')
    stock._stock_rpc_client = Mock()
    client=stock._stock_rpc_client.return_value
    def rpc(name, params):
        assert name == 'erp_finance_transaction'
        act=params['p_action']; key={'ACCOUNT':'compte_id','PAYMENT':'reglement_id','ALLOCATE':'lettrage_id'}[act]
        return types.SimpleNamespace(execute=lambda:types.SimpleNamespace(
            data={'operation_id':params['p_operation_id'],'action':act,key:'ID-006'}))
    client.rpc.side_effect=rpc
    monkeypatch.setitem(sys.modules,'core.db_service',db)
    monkeypatch.setitem(sys.modules,'modules.stocks.service',stock)
    spec=importlib.util.spec_from_file_location('finance006_validation', ROOT/'modules/finance/service.py')
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod, client

@pytest.mark.parametrize('invalid',['Marchandises','VENTE','',None,'Autre'])
def test_invalid_account_type_rejected_before_rpc(finance,invalid):
    mod, client=finance
    with pytest.raises(ValueError):
        mod.creer_compte('Compte','' if invalid is None else invalid,'512','0.00')
    client.rpc.assert_not_called()

@pytest.mark.parametrize('allowed',['BANQUE','Banque','Caisse','Tiers client','Tiers fournisseur'])
def test_supported_account_types_still_allowed(finance, allowed):
    mod, client=finance
    assert mod.creer_compte('Compte',allowed,'512','0.00',operation_id='FIN-006')=='ID-006'
    assert client.rpc.call_args.args[1]['p_payload']['type_compte']==allowed


def test_sql_rls_and_server_roles():
    s=(ROOT/'sql/006_atomic_finance.sql').read_text(encoding='utf-8')
    for table in ('erp_finance_operations','erp_finance_outbox'):
        assert 'ALTER TABLE public.'+table+' ENABLE ROW LEVEL SECURITY;' in s
        assert 'ON public.'+table+' FOR ALL TO service_role' in s
    assert 'SECURITY INVOKER' in s
    assert 'REVOKE ALL ON FUNCTION public.erp_finance_transaction' in s


def test_sql_account_and_partner_integrity_guards():
    s=(ROOT/'sql/006_atomic_finance.sql').read_text(encoding='utf-8')
    assert 'v_cash_type NOT IN' in s
    assert 'v_counter_type NOT IN' in s
    assert "WHERE client_id=p_payload->>'partenaire_id' AND actif='OUI'" in s
    assert "WHERE fournisseur_id=p_payload->>'partenaire_id' AND actif='OUI'" in s
    assert "'ANNULE','REJETE','PAYEE'" in s

@pytest.mark.parametrize('expression',[
    "v_direction || ' ' || (p_payload->>'reference_trace')",
    "'Contrepartie ' || (p_payload->>'reference_trace')",
])
def test_sql_payment_labels_parenthesize_json_extraction(expression):
    sql=(ROOT/'sql/006_atomic_finance.sql').read_text(encoding='utf-8')
    assert expression in sql
    # Avoid PostgreSQL evaluating text || jsonb before ->> on a composed label.
    assert not __import__('re').search(r'\|\|\s*p_payload\s*->>', sql)
