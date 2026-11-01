import pandas as pd
import pytest
from core.indicateurs_tresorerie import validated_payments, cash_balances
from core.strict_reads import DataReadError
from modules.dashboards import service


def payment(**kw):
    return dict(dict(compte_id='B',type_flux='ENCAISSEMENT',statut='VALIDE',montant_total=100,montant_alloue=20,date_reglement='2026-10-01'),**kw)


def accounts():
    return pd.DataFrame([dict(compte_id='B',nom_compte='Banque',type_compte='Banque',solde_initial=50),
                         dict(compte_id='T',nom_compte='Client',type_compte='Tiers Client',solde_initial=999)])


def test_balance_validated_cash_only_future_excluded():
    p=validated_payments(pd.DataFrame([payment(),payment(type_flux='DECAISSEMENT',montant_total=30),
        payment(statut='BROUILLON'),payment(statut='ANNULE'),payment(date_reglement='2026-12-01')]))
    b=cash_balances(accounts(),p,'2026-11-01')
    assert b['compte_id'].tolist()==['B']
    assert b['solde'].tolist()==[120]


@pytest.mark.parametrize('kw',[dict(montant_total=None),dict(montant_alloue=101),dict(montant_alloue=-1),
    dict(montant_total=-1),dict(date_reglement=None),dict(type_flux='OTHER'),dict(statut='OTHER')])
def test_invalid_payment_is_unavailable(kw):
    with pytest.raises(DataReadError):
        validated_payments(pd.DataFrame([payment(**kw)]))


@pytest.mark.parametrize('account_id',['missing','T',None])
def test_unknown_or_non_cash_payment_account(account_id):
    with pytest.raises(DataReadError):
        cash_balances(accounts(),validated_payments(pd.DataFrame([payment(compte_id=account_id)])),'2026-11-01')


def test_finance_empty_period_keeps_current_balances(monkeypatch):
    monkeypatch.setattr(service,'fetch_data',lambda t: accounts().to_dict('records') if t=='comptes' else [payment()])
    monkeypatch.setattr(service,'get_local_now',lambda:pd.Timestamp('2026-11-01'))
    k=service.get_kpis_finance(pd.Timestamp('2026-11-01'),pd.Timestamp('2026-11-30'))
    assert k['flux_entrants']==0 and k['repartition_comptes']['solde'].tolist()==[150]


def test_period_flow_and_allocation(monkeypatch):
    monkeypatch.setattr(service,'fetch_data',lambda t: accounts().to_dict('records') if t=='comptes' else [payment(),payment(statut='BROUILLON')])
    monkeypatch.setattr(service,'get_local_now',lambda:pd.Timestamp('2026-11-01'))
    k=service.get_kpis_finance(pd.Timestamp('2026-10-01'),pd.Timestamp('2026-10-31'))
    assert k['flux_entrants']==100 and k['taux_lettrage']==20


@pytest.mark.parametrize('due,status,expected',[('2026-10-31','EN_ATTENTE',1),('2026-11-01','EN_ATTENTE',0),
    ('2026-10-31','PARTIELLEMENT_RECEPTIONNE',1),(None,'RECEPTIONNE',0),(None,'ANNULE',0)])
def test_purchase_empty_period_keeps_global_lateness(monkeypatch,due,status,expected):
    monkeypatch.setattr(service,'fetch_data',lambda t:[dict(date_voulue=due,statut=status)] if t=='commandes_achats' else [])
    monkeypatch.setattr(service,'fetch_data_by_date_range',lambda *a:[])
    monkeypatch.setattr(service,'get_local_now',lambda:pd.Timestamp('2026-11-01 18:00'))
    k=service.get_kpis_achats(pd.Timestamp('2026-11-01'),pd.Timestamp('2026-11-30'))
    assert k['commandes_retard']==expected and k['montant_total']==0


def test_purchase_missing_due_date_not_false_zero(monkeypatch):
    monkeypatch.setattr(service,'fetch_data',lambda t:[dict(date_voulue=None,statut='EN_ATTENTE')] if t=='commandes_achats' else [])
    monkeypatch.setattr(service,'fetch_data_by_date_range',lambda *a:[])
    with pytest.raises(DataReadError):
        service.get_kpis_achats(pd.Timestamp('2026-11-01'),pd.Timestamp('2026-11-30'))
