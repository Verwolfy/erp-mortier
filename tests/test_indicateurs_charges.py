"""Paie/OPEX : exemples fictifs, tests hors réseau."""
import pandas as pd
import pytest
from core.indicateurs_charges import payroll_net_for_period, supplier_operating_payments
from core.strict_reads import DataReadError
from modules.dashboards import service


def payroll(rows, start='2026-11-01', end='2026-11-30'):
    return payroll_net_for_period(pd.DataFrame(rows), start, end)


def pay(**changes):
    return dict(dict(annee=2026, mois=11, net_a_payer=100), **changes)


def payment(**changes):
    return dict(dict(type_flux='DECAISSEMENT', statut='VALIDE', partenaire_id='S1', montant_total=50), **changes)


def opex(rows, suppliers=None):
    if suppliers is None:
        suppliers = [dict(fournisseur_id='S1', categorie='Services OPEX')]
    return supplier_operating_payments(pd.DataFrame(rows), pd.DataFrame(suppliers))


def test_payroll_filters_month_and_year():
    assert payroll([pay(),pay(annee=2025),pay(mois=10),pay(mois=12)]) == 100


def test_payroll_cross_year_and_leap_february():
    assert payroll([pay(annee=2025,mois=12),pay(mois=1),pay(mois=2)], '2025-12-01','2026-01-31') == 200
    assert payroll([pay(annee=2024,mois=2)], '2024-02-01','2024-02-29') == 100


@pytest.mark.parametrize('start,end',[('2026-11-02','2026-11-30'),('2026-11-01','2026-11-29')])
def test_partial_month_never_invents_prorata(start,end):
    with pytest.raises(DataReadError):
        payroll([pay()],start,end)


def test_no_relevant_payroll_allows_daily_view():
    assert payroll([pay(mois=10)],'2026-11-01','2026-11-02') == 0
    assert payroll([],'2026-11-01','2026-11-02') == 0


@pytest.mark.parametrize('change',[dict(mois=0),dict(mois=13),dict(mois=1.5),
    dict(annee=None),dict(annee=True),dict(net_a_payer=None),dict(net_a_payer=-1),
    dict(net_a_payer=float('inf'))])
def test_invalid_payroll_never_becomes_zero(change):
    with pytest.raises(DataReadError):
        payroll([pay(**change)])


def test_payroll_is_recorded_net_not_payment_or_employer_cost():
    assert payroll([pay(statut_paiement='NON_PAYE'),pay(statut_paiement='PAYEE')]) == 200


def test_only_validated_outgoing_opex():
    assert opex([payment(),payment(statut='BROUILLON'),payment(statut='ANNULE'),
        payment(type_flux='ENCAISSEMENT'),payment(partenaire_id='S2')],
        [dict(fournisseur_id='S1',categorie='services opex'),dict(fournisseur_id='S2',categorie='MP')]) == 50


@pytest.mark.parametrize('suppliers',[[],[dict(fournisseur_id='other',categorie='OPEX')],
    [dict(fournisseur_id='S1',categorie=None)], [dict(fournisseur_id='S1',categorie='')],
    [dict(fournisseur_id='S1',categorie='OPEX')]*2])
def test_missing_or_ambiguous_supplier_cannot_hide_payment(suppliers):
    with pytest.raises(DataReadError):
        opex([payment()], suppliers)


@pytest.mark.parametrize('change',[dict(montant_total=None),dict(montant_total=-1),
    dict(montant_total='bad'),dict(montant_total=True),dict(statut='UNKNOWN'),
    dict(partenaire_id=None),dict(type_flux='UNKNOWN')])
def test_invalid_payment_is_unavailable(change):
    with pytest.raises(DataReadError):
        opex([payment(**change)])


def test_empty_or_only_incoming_payments_need_no_suppliers():
    assert opex([],[]) == 0
    assert opex([payment(type_flux='ENCAISSEMENT')],[]) == 0


def test_pnl_integrates_monthly_net_and_validated_opex(monkeypatch):
    tables = {'fiches_de_paie':[pay(),pay(mois=10)],
              'fournisseurs':[dict(fournisseur_id='S1',categorie='OPEX')]}
    monkeypatch.setattr(service,'fetch_data',lambda name: tables.get(name,[]))
    monkeypatch.setattr(service,'fetch_data_by_date_range',
        lambda name,*args: [payment(),payment(statut='BROUILLON')] if name=='reglements' else [])
    k=service.get_kpis_pnl(pd.Timestamp('2026-11-01'),pd.Timestamp('2026-11-30'))
    assert (k['opex_salaires'],k['opex_fournisseurs'],k['ebitda']) == (100,50,-150)
