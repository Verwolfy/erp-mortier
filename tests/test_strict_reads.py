"""Lectures sans réseau : bornes, pagination, confidentialité et pannes."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from core import strict_reads as reads


class Query:
    def __init__(self, client, table):
        self.client, self.table = client, table
        self.filters, self.projection, self.sort, self.bounds = [], '*', None, None

    def select(self, projection, *, count):
        assert count == 'exact'
        self.projection = projection
        return self

    def gte(self, col, value):
        self.filters.append(('gte', col, value))
        return self

    def lte(self, col, value):
        self.filters.append(('lte', col, value))
        return self

    def order(self, col):
        self.sort = col
        return self

    def range(self, start, end):
        self.bounds = start, end
        return self

    def execute(self):
        self.client.calls.append(self)
        if self.client.responses is not None:
            response = self.client.responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response
        data = self.client.tables.get(self.table, [])
        for op, col, value in self.filters:
            data = [r for r in data if r[col] >= value] if op == 'gte' else [r for r in data if r[col] <= value]
        data = sorted(data, key=lambda r: r[self.sort])
        total = len(data)
        start, end = self.bounds
        data = data[start:min(end + 1, start + self.client.api_cap)]
        if self.projection != '*':
            data = [{k:r[k] for k in self.projection.split(',')} for r in data]
        return SimpleNamespace(data=data, count=total)


@pytest.fixture
def env(monkeypatch):
    client = SimpleNamespace(tables={}, responses=None, calls=[], api_cap=1000)
    client.table = lambda table: Query(client, table)
    guard = Mock()
    monkeypatch.setattr(reads.db, '_require_read_permission', guard)
    monkeypatch.setattr(reads.db, 'get_supabase_client', lambda: client)
    return client, guard


def reply(data, count):
    return SimpleNamespace(data=data, count=count)


def test_reads_beyond_api_limit_and_revalidates_every_page(env):
    client, guard = env
    client.api_cap = 200  # API configured below requested page_size.
    client.tables['pipeline'] = [{'opportunite_id':f'O{i:04}'} for i in range(1203)]
    rows = reads.fetch_data_strict('pipeline')
    assert len(rows) == 1203
    assert guard.call_count == 7
    assert [q.bounds[0] for q in client.calls] == [0,200,400,600,800,1000,1200]
    assert all(q.sort == 'opportunite_id' for q in client.calls)


def test_filters_apply_on_every_page_with_inclusive_dates(env):
    client, _ = env
    client.api_cap = 1
    client.tables['factures'] = [
        {'facture_id':str(i),'date':d} for i,d in enumerate(
            ['2026-09-30','2026-10-01','2026-10-31','2026-11-01'])]
    rows = reads.fetch_data_by_date_range_strict('factures','date','2026-10-01','2026-10-31')
    assert [r['date'] for r in rows] == ['2026-10-01','2026-10-31']
    assert all(len(q.filters) == 2 for q in client.calls)


def test_verified_empty_is_valid(env):
    assert reads.fetch_data_strict('pipeline') == []


@pytest.mark.parametrize('responses', [
    [reply(None,0)], [reply({},0)], [reply([],None)], [reply([],True)],
    [reply([],1)], [reply([],10001)], [reply([{}],1)],
    [reply([{'opportunite_id':True}],1)], [reply([{'opportunite_id':''}],1)],
    [reply([{'opportunite_id':'a'},{'opportunite_id':'a'}],2)],
    [reply([{'opportunite_id':'a'}],2), reply([{'opportunite_id':'a'}],2)],
    [reply([{'opportunite_id':'a'}],2), reply([],2)],
    [reply([{'opportunite_id':'a'}],2), reply([{'opportunite_id':'b'}],3)],
    [reply([{'opportunite_id':'a'},{'opportunite_id':'b'}],1)],
    [reply([{'opportunite_id':'a'}],2), ConnectionError('secret token')],
])
def test_invalid_or_partial_result_is_never_returned(env, responses):
    client, _ = env
    client.responses = responses.copy()
    with pytest.raises(reads.DataReadError) as error:
        reads.fetch_data_strict('pipeline')
    assert 'secret token' not in str(error.value)


def test_access_revoked_between_pages(env):
    client, guard = env
    client.responses = [reply([{'opportunite_id':'a'}],2)]
    guard.side_effect = [None, PermissionError('denied')]
    with pytest.raises(PermissionError):
        reads.fetch_data_strict('pipeline')
    assert len(client.calls) == 1


def test_denied_access_does_not_query_data(env):
    client, guard = env
    guard.side_effect = PermissionError('denied')
    with pytest.raises(PermissionError):
        reads.fetch_data_strict('pipeline')
    assert client.calls == []


def test_private_projection_preserved(env):
    client, _ = env
    client.tables['users'] = [dict(user_id='u1', nom='A', login='a',role='ADMIN',actif='OUI',hash_mdp='secret')]
    rows = reads.fetch_data_strict('users')
    assert 'hash_mdp' not in rows[0]
    assert client.calls[0].projection == 'user_id,nom,login,role,actif'


@pytest.mark.parametrize('kwargs', [
    {'page_size':True},{'page_size':0},{'max_rows':0}, {'max_rows':100001},
    {'date_column':'hash_mdp','start_date':'2026-01-01','end_date':'2026-12-31'},
    {'date_column':'date','start_date':'2026-12-31','end_date':'2026-01-01'},
    {'date_column':'date','start_date':'2026-13-01','end_date':'2026-12-31'},
    {'date_column':'date','start_date':None,'end_date':'2026-12-31'},
])
def test_invalid_request_never_queries(env, kwargs):
    with pytest.raises(ValueError):
        reads.fetch_data_strict('factures', **kwargs)
    assert env[0].calls == []


def test_read_section_skips_false_zero_and_continues_next_section(monkeypatch):
    import streamlit as st
    error, metric = Mock(), Mock()
    monkeypatch.setattr(st, 'error', error)
    with reads.read_section('Ventes'):
        raise reads.DataReadError('server private details')
        metric('CA', 0)
    metric.assert_not_called()
    assert 'indisponibles' in error.call_args.args[0]
    assert 'private' not in error.call_args.args[0]
    with reads.read_section('Stocks'):
        metric('Stock', 10)
    metric.assert_called_once_with('Stock', 10)


def test_unrelated_programming_error_is_not_swallowed():
    with pytest.raises(KeyError):
        with reads.read_section('CRM'):
            raise KeyError('missing column')


def test_crm_listing_does_not_turn_network_error_into_empty(env):
    from modules.crm.service import get_pipeline
    env[0].responses = [ConnectionError('private response')]
    with pytest.raises(reads.DataReadError):
        get_pipeline()


def test_dashboard_direction_does_not_turn_network_error_into_zero(env):
    from modules.dashboards.service import get_kpis_direction
    env[0].responses = [ConnectionError('private response')]
    with pytest.raises(reads.DataReadError):
        get_kpis_direction()


def test_strict_reference_list_propagates_failure(env):
    from core.listes_service import get_liste
    env[0].responses = [ConnectionError('private response')]
    with pytest.raises(reads.DataReadError):
        get_liste('TypeInteractionCRM', strict=True)
