from decimal import Decimal
from uuid import uuid4
from types import SimpleNamespace
import pytest

from erp_engine.gateway import ERPGateway, ERPServiceError
from erp_engine.formulation import ValidationError

COMPANY = 'cfc2ebd8-9b85-4097-9aab-943e7d0d9e81'
RECIPE = 'd836e47a-a540-4095-aa50-b21e7be7f3dc'
OPERATION = '609b9891-a3c6-451f-b4de-d0fadcb38ad5'


class MockQuery:
    def __init__(self, response=None, fail=False):
        self.response, self.fail = response, fail
    def execute(self):
        if self.fail:
            raise RuntimeError('SIMULATED_SECRET_API_KEY')
        return SimpleNamespace(data=self.response)


class MockClient:
    def __init__(self, response=None, fail=False):
        self.calls = []
        self.response, self.fail = response if response is not None else {'status':'ok'}, fail
    def rpc(self, function_name, params):
        self.calls.append((function_name, params))
        return MockQuery(self.response, self.fail)


def test_receipt_params_exact_decimal_and_uuid():
    fake = MockClient({'status':'ok', 'quantity':'25'})
    result = ERPGateway(fake).receive_lot(
        company_id=COMPANY, item_code='RESINE', lot_code='MP-2026-0001',
        quantity=Decimal('25.01'), unit_cost='102.55', operation_id=OPERATION)
    assert result['status'] == 'ok'
    name, params = fake.calls[0]
    assert name == 'erp_receive_lot'
    assert params['p_quantity'] == '25.01'
    assert params['p_unit_cost'] == '102.55'
    assert params['p_operation_id'] == OPERATION


def test_manufacturing_params():
    fake = MockClient([{'status':'ok','consumed_lots':[]}])
    result = ERPGateway(fake).close_manufacturing(
        company_id=COMPANY, recipe_id=RECIPE, finished_lot='PF-123',
        output_quantity='1000.000001', operation_id=OPERATION)
    assert result['status'] == 'ok'
    name, params = fake.calls[0]
    assert name == 'erp_manufacture'
    assert params['p_output_quantity'] == '1000.000001'


@pytest.mark.parametrize('invalid_qty',[0,'-1','NaN','1.0000001',float('inf'),1.2])
def test_bad_values_block_rpc(invalid_qty):
    fake = MockClient()
    with pytest.raises(ValidationError):
        ERPGateway(fake).receive_lot(company_id=COMPANY,item_code='MP',lot_code='LOT',
            quantity=invalid_qty,unit_cost=1,operation_id=OPERATION)
    assert fake.calls == []


def test_invalid_uuid_block_rpc():
    fake = MockClient()
    with pytest.raises(ValidationError):
        ERPGateway(fake).close_manufacturing(company_id=COMPANY,recipe_id='wrong',
            finished_lot='PF',output_quantity=1,operation_id=OPERATION)
    assert fake.calls == []


def test_fail_closed_and_no_secret_exposure():
    fake = MockClient(fail=True)
    with pytest.raises(ERPServiceError) as e:
        ERPGateway(fake).receive_lot(company_id=COMPANY,item_code='MP',lot_code='LOT',
            quantity=1,unit_cost=1,operation_id=OPERATION)
    assert 'SIMULATED_SECRET' not in str(e.value)


def test_unexpected_response_refused():
    fake = MockClient({'wrong': True})
    with pytest.raises(ERPServiceError):
        ERPGateway(fake).close_manufacturing(company_id=COMPANY,recipe_id=RECIPE,
            finished_lot='PF',output_quantity=1,operation_id=OPERATION)


def test_sql_hidden_schema_and_rpc_permissions_declared():
    from pathlib import Path
    sql = (Path(__file__).parents[1] / 'sql' / '001_atomic_manufacturing.sql').read_text()
    assert 'SECURITY DEFINER SET search_path = \'\'' in sql
    assert 'ENABLE ROW LEVEL SECURITY' in sql
    assert 'FOR UPDATE' in sql
    assert 'ON CONFLICT DO NOTHING' in sql
    assert 'GRANT EXECUTE ON FUNCTION public.erp_manufacture' in sql


def test_misleading_item_codes_rejected():
    fake = MockClient()
    with pytest.raises(ValidationError):
        ERPGateway(fake).receive_lot(company_id=COMPANY,item_code=' RESIN ',lot_code='LOT',
           quantity=1,unit_cost=1,operation_id=OPERATION)
    assert fake.calls == []


def test_duplicate_retry_key_preserved_by_client():
    fake = MockClient({'status':'ok'})
    api = ERPGateway(fake)
    kwargs = dict(company_id=COMPANY, recipe_id=RECIPE, finished_lot='PF-001',
                  output_quantity='10',operation_id=OPERATION)
    api.close_manufacturing(**kwargs)
    api.close_manufacturing(**kwargs)
    assert fake.calls[0][1]['p_operation_id'] == fake.calls[1][1]['p_operation_id']
