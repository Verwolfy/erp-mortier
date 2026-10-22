"""Ventes 005 : contrôles de sécurité locaux sans accès au Supabase réel."""
from __future__ import annotations
from decimal import Decimal
from pathlib import Path
import importlib.util
import sys
import types
import pytest

ROOT = Path(__file__).resolve().parents[1]

def service_with_stubs(monkeypatch):
    from unittest.mock import MagicMock
    db = types.ModuleType('core.db_service')
    db.fetch_data=MagicMock(return_value=[])
    db.fetch_data_filtered=MagicMock(return_value=[])
    db.get_supabase_client=MagicMock()
    db.check_server_permission=MagicMock(return_value=True)
    utils = types.ModuleType('core.utils'); utils.get_local_now=MagicMock()
    stocks = types.ModuleType('modules.stocks.service'); stocks._stock_rpc_client=MagicMock()
    monkeypatch.setitem(sys.modules,'core.db_service',db)
    monkeypatch.setitem(sys.modules,'core.utils',utils)
    monkeypatch.setitem(sys.modules,'modules.stocks.service',stocks)
    name='ventes_test_005_standalone'
    spec=importlib.util.spec_from_file_location(name,ROOT/'modules/ventes/service.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module,stocks

def test_invoice_integer_quantities(monkeypatch):
    mod,_=service_with_stubs(monkeypatch)
    with pytest.raises(ValueError,match='unités entières'):
        mod._invoice_lines([{'sku_id':'SKU-001','quantite':'1.5','prix_unitaire':'120','remise':0}])
    lines,amount=mod._invoice_lines([{'sku_id':'SKU-001','quantite':'2','prix_unitaire':'120','remise':'20'}])
    assert amount==Decimal('220.00')
    assert lines[0]['quantite']=='2'

def test_shipping_integer_quantities(monkeypatch):
    mod,stocks=service_with_stubs(monkeypatch)
    with pytest.raises(ValueError,match='unités entières'):
        mod.creer_bon_livraison('CV-1','T','Z',[{'sku_id':'SKU-001','quantite_livree':'1.5'}])
    stocks._stock_rpc_client.assert_not_called()

def test_sql_rls_and_safe_invoice_link():
    s=(ROOT/'sql/005_atomic_sales.sql').read_text(encoding='utf-8')
    assert 'ALTER TABLE public.erp_sales_operations ENABLE ROW LEVEL SECURITY' in s
    assert 'ALTER TABLE public.erp_sales_outbox ENABLE ROW LEVEL SECURITY' in s
    assert 'VALUES(v_invoice_id,NULL' in s
    assert 'v_line.quantite <> trunc(v_line.quantite)' in s
    assert 'v_line.quantite_livree <> trunc(v_line.quantite_livree)' in s
    assert 'v_order.statut NOT IN' in s
    assert 'GRANT EXECUTE ON FUNCTION public.erp_sale_transaction' in s

def test_ui_statuses_restricted():
    s=(ROOT/'modules/ventes/views.py').read_text(encoding='utf-8')
    assert 'orders = orders[orders["statut"].isin(_EXPEDIABLE_STATES)]' in s
    assert 'current_context = (client_id, type_doc, origine)' in s
