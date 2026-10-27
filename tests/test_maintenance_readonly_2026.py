"""Protection des anciens scripts de maintenance: AUCUNE écriture Supabase."""
from __future__ import annotations
import ast
import importlib.util
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows
        self.start = 0
        self.end = 499
    def select(self, *args): return self
    def order(self, *args): return self
    def range(self, start, end):
        self.start, self.end = start, end
        return self
    def execute(self):
        return type('Response', (), {'data': self.rows[self.start:self.end+1]})()
    def insert(self, *args): raise AssertionError('INTERDIT insert')
    def update(self, *args): raise AssertionError('INTERDIT update')
    def delete(self, *args): raise AssertionError('INTERDIT delete')


class FakeClient:
    def __init__(self, tables): self.tables = tables
    def table(self, name): return FakeQuery(self.tables.get(name, []))


def _stock(): return _module(ROOT/'scripts'/'recalculer_stock.py', 'readonly_stock')


def test_stock_source_has_no_mutators():
    source = (ROOT/'scripts'/'recalculer_stock.py').read_text(encoding='utf8')
    tree = ast.parse(source)
    forbidden = {'insert', 'update', 'upsert', 'delete'}
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute) and n.func.attr in forbidden]


def test_import_source_has_no_mutators():
    source = (ROOT/'import_data.py').read_text(encoding='utf8')
    tree = ast.parse(source)
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and n.func.attr in {'insert', 'update', 'upsert', 'delete'}]


def test_import_preview_only(tmp_path):
    mod = _module(ROOT/'import_data.py', 'readonly_seed')
    dest = tmp_path/'reference.json'
    rows = mod.importer_referentiels(dest)
    assert len(rows) > 100
    assert json.loads(dest.read_text(encoding='utf8')) == rows


def test_import_missing_parent_fails(tmp_path):
    mod = _module(ROOT/'import_data.py', 'readonly_seed_alt')
    with pytest.raises(FileNotFoundError):
        mod.importer_referentiels(tmp_path/'notexist'/'ref.json')


def test_mp_equal():
    mod = _stock()
    c = FakeClient({'mouvements': [
        {'mouvement_id':'m1','mp_id':'MP1','type_mouvement':'ENTREE','quantite':'10.50'},
        {'mouvement_id':'m2','mp_id':'MP1','type_mouvement':'SORTIE','quantite':'2.25'}],
        'stock_actuel':[{'mp_id':'MP1','quantite_disponible':'8.25'}]})
    assert mod.auditer_et_corriger_stock_mp(c)['ecarts'] == []


def test_mp_discrepancy():
    mod = _stock()
    c = FakeClient({'mouvements': [{'mouvement_id':'1','mp_id':'MP1','type_mouvement':'ENTREE','quantite':10}],
                    'stock_actuel':[{'mp_id':'MP1','quantite_disponible':8}]})
    result=mod.auditer_et_corriger_stock_mp(c)
    assert result['ecarts'][0]['ecart'] == '2'


def test_pf_discrepancy():
    mod = _stock()
    c = FakeClient({'mouvements_pf': [{'mouvement_pf_id':'1','sku_id':'SKU','type_mouvement':'ENTREE','quantite':'2'}],
                    'stock_actuel_pf':[]})
    assert mod.auditer_et_corriger_stock_pf(c)['ecarts'][0]['stock_actuel'] == 'ABSENT'


@pytest.mark.parametrize('kind', ['AJUSTEMENT', 'SORTIE_RETOUR', None, ''])
def test_unknown_movement_fails_closed(kind):
    mod = _stock()
    c = FakeClient({'mouvements':[{'mouvement_id':'1','mp_id':'X','type_mouvement':kind,'quantite':2}]})
    with pytest.raises(mod.StockAuditError):
        mod.auditer_et_corriger_stock_mp(c)


@pytest.mark.parametrize('qty', ['oops', None, 'NaN', '-3', '0'])
def test_invalid_movement_quantity_fails(qty):
    mod = _stock()
    c = FakeClient({'mouvements':[{'mouvement_id':'1','mp_id':'X','type_mouvement':'ENTREE','quantite':qty}]})
    with pytest.raises(mod.StockAuditError):
        mod.auditer_et_corriger_stock_mp(c)


def test_pages_over_500():
    mod=_stock()
    moves=[{'mouvement_id':f'M{i:03}', 'mp_id':'M', 'type_mouvement':'ENTREE', 'quantite':'1'}
           for i in range(510)]
    c=FakeClient({'mouvements':moves, 'stock_actuel':[{'mp_id':'M','quantite_disponible':510}]})
    assert mod.auditer_et_corriger_stock_mp(c)['ecarts'] == []


def test_duplicate_stock_ids_stop():
    mod=_stock()
    c=FakeClient({'stock_actuel':[{'mp_id':'M','quantite_disponible':1},
                                  {'mp_id':'M','quantite_disponible':2}]})
    with pytest.raises(mod.StockAuditError):
        mod.auditer_et_corriger_stock_mp(c)
