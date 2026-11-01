"""Régressions des indicateurs ; données fictives locales, aucun accès serveur."""
from datetime import datetime, timezone
import pandas as pd
import pytest
from core.indicateurs_factures import validated_documents, open_receivables, ageing_balance
from core.strict_reads import DataReadError
from modules.dashboards import service


def invoice(key='F1', **changes):
    row = dict(facture_id=key, client_id='C1', type_facture='FactureClient',
               statut='VALIDE', date='2026-11-01', date_echeance='2026-11-30',
               montant_ht=100, montant_ttc=120, montant_paye=0, montant_timbre=0)
    return dict(row, **changes)


@pytest.fixture
def data(monkeypatch):
    tables = {}
    monkeypatch.setattr(service, 'fetch_data', lambda table: tables.get(table, []))
    monkeypatch.setattr(service, 'fetch_data_by_date_range',
                        lambda table, col, start, end: [r for r in tables.get(table, []) if start <= r[col] <= end])
    monkeypatch.setattr(service, 'get_local_now', lambda: datetime(2026, 11, 1, 18, tzinfo=timezone.utc))
    return tables


def sales():
    return service.get_kpis_ventes(pd.Timestamp('2026-11-01'), pd.Timestamp('2026-11-30'))


def test_validated_gross_invoices_and_separate_credits(data):
    data['factures'] = [invoice(), invoice('draft', statut='BROUILLON'),
        invoice('cancelled', statut='ANNULE'),
        invoice('credit', type_facture='FactureAvoir', montant_ht=-20, montant_ttc=-24)]
    k = sales()
    assert (k['ca_ht'], k['ca_ttc'], k['nb_factures'], k['panier_moyen'], k['taux_avoirs']) == (100, 120, 1, 120, 20)
    assert k['top_clients']['montant_ttc'].tolist() == [120]
    assert sum(k['balance_agee'].values()) == 120
    assert service.get_kpis_direction()['ca_mois'] == 100


def test_empty_period_preserves_old_partial_receivable(data):
    data['factures'] = [invoice(date='2026-09-01', date_echeance='2026-09-01', montant_paye=20),
                        invoice('paid', montant_paye=120, date='2026-09-01', date_echeance=None)]
    k = sales()
    assert k['ca_ht'] == 0 and k['nb_factures'] == 0 and k['top_clients'].empty
    assert k['balance_agee']['+ de 60 jrs'] == 100
    assert service.get_kpis_direction()['impayes_30j'] == 100


@pytest.mark.parametrize('days,bucket', [(0,'Non échu'),(-1,'Non échu'),(1,'1 à 30 jours'),
    (30,'1 à 30 jours'),(31,'31 à 60 jours'),(60,'31 à 60 jours'),(61,'+ de 60 jrs')])
def test_ageing_uses_calendar_days(days, bucket):
    due = (pd.Timestamp('2026-11-01') - pd.Timedelta(days=days)).strftime('%Y-%m-%d')
    docs = validated_documents(pd.DataFrame([invoice(date_echeance=due)]))
    balance = ageing_balance(open_receivables(docs, pd.Timestamp('2026-11-01 23:59:59')))
    assert balance[bucket] == 120 and sum(balance.values()) == 120


@pytest.mark.parametrize('changes', [dict(montant_ht=None),dict(montant_ttc='bad'),
    dict(montant_paye=float('inf')),dict(montant_ht=True),dict(montant_paye=121),
    dict(montant_paye=-1),dict(statut='PARTIELLE'),dict(type_facture='unknown'),
    dict(date=None),dict(client_id=None),dict(type_facture='FactureAvoir')])
def test_invalid_document_is_unavailable_not_zero(data, changes):
    data['factures'] = [invoice(**changes)]
    with pytest.raises(DataReadError):
        sales()


def test_missing_due_date_blocks_only_open_invoice(data):
    data['factures'] = [invoice(date_echeance=None)]
    with pytest.raises(DataReadError):
        sales()
    data['factures'][0]['montant_paye'] = 120
    assert sum(sales()['balance_agee'].values()) == 0


def test_empty_tables(data):
    assert sales()['ca_ht'] == 0
    assert service.get_kpis_direction()['impayes_30j'] == 0


def test_pnl_costs_only_validated_client_invoices(data):
    data['factures'] = [invoice(), invoice('draft', statut='BROUILLON'),
        invoice('credit', type_facture='FactureAvoir', montant_ht=-20, montant_ttc=-24)]
    data['lignes_facture'] = [dict(facture_id='F1', sku_id='P1', quantite=2),
                            dict(facture_id='draft', sku_id='absent', quantite=999),
                            dict(facture_id='credit', sku_id='absent', quantite=-1)]
    data['stock_actuel_pf'] = [dict(sku_id='P1', cout_revient=30)]
    k = service.get_kpis_pnl(pd.Timestamp('2026-11-01'), pd.Timestamp('2026-11-30'))
    assert (k['ca_ht'], k['cogs'], k['marge_brute']) == (100,60,40)


@pytest.mark.parametrize('costs', [[],[dict(sku_id='P1', cout_revient=None)],
    [dict(sku_id='other', cout_revient=1)], [dict(sku_id='P1',cout_revient=-1)],
    [dict(sku_id='P1',cout_revient=1),dict(sku_id='P1',cout_revient=2)]])
def test_pnl_missing_or_ambiguous_cost_is_not_zero(data, costs):
    data['factures'] = [invoice()]
    data['lignes_facture'] = [dict(facture_id='F1', sku_id='P1', quantite=2)]
    data['stock_actuel_pf'] = costs
    with pytest.raises(DataReadError):
        service.get_kpis_pnl(pd.Timestamp('2026-11-01'), pd.Timestamp('2026-11-30'))
