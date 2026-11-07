"""Régressions KPI et graphiques ERP : scénarios locaux, sans Supabase.

Objectif : ratios honnêtes, périodes cohérentes, prix comparables, aucun
zéro de remplacement pour une valeur invalide et aucun KPI industriel inventé.
"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pandas as pd
import pytest

from core.strict_reads import DataReadError
from modules.dashboards import service, views


START, END = pd.Timestamp("2026-11-01"), pd.Timestamp("2026-11-30")


def _read_fixture(monkeypatch, tables):
    monkeypatch.setattr(service, "fetch_data", lambda name: [dict(r) for r in tables.get(name, [])])
    monkeypatch.setattr(
        service, "fetch_data_by_date_range",
        lambda table, date_col, start, end: [
            dict(r) for r in tables.get(table, [])
            if isinstance(r.get(date_col), str) and start <= r[date_col] <= end],
    )
    monkeypatch.setattr(service, "get_local_now", lambda: datetime(2026, 11, 5, 12, 0))


def _invoice(key, day, amount):
    return {
        "facture_id": key, "client_id": "CLIENT-A", "statut": "VALIDE",
        "type_facture": "FactureClient", "date": day,
        "date_echeance": "2026-11-30", "montant_ht": amount,
        "montant_ttc": amount * 1.19, "montant_paye": 0, "montant_timbre": 0,
    }


def test_sales_daily_trend_is_real_and_sorted(monkeypatch):
    _read_fixture(monkeypatch, {
        "factures": [
            _invoice("F-3", "2026-11-03", 20),
            _invoice("F-1", "2026-11-01", 10),
            _invoice("F-2", "2026-11-01", 5),
            {**_invoice("F-DRAFT", "2026-11-02", 500), "statut": "BROUILLON"},
        ]})
    kpi = service.get_kpis_ventes(START, END)
    trend = kpi["evolution_facturation"]
    assert trend["Facturation HT (DZD)"].tolist() == [15, 20]
    assert trend["Date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2026-11-01", "2026-11-03",
    ]
    assert kpi["ca_ht"] == 35


def test_sales_no_validated_invoice_does_not_draw_fake_zero_line(monkeypatch):
    _read_fixture(monkeypatch, {"factures": []})
    kpi = service.get_kpis_ventes(START, END)
    assert kpi["evolution_facturation"].empty
    assert kpi["nb_factures"] == 0


def _purchase(price, fx, cur, day, key):
    return ({"commande_achat_id": key, "fournisseur_id": "FOU",
             "date_commande": day, "date_voulue": "2026-11-25",
             "devise": cur, "taux_change": fx, "statut": "EN_ATTENTE",
             "montant_total_local": price * fx},
            {"commande_achat_id": key, "mp_id": "MP-A",
             "unite_cond": "KG", "prix_unitaire": price})


def test_purchase_price_trend_converts_fx_without_mixing_currency(monkeypatch):
    first, line1 = _purchase(10, 150, "EUR", "2026-11-01", "A1")
    second, line2 = _purchase(1200, 1, "DZD", "2026-11-03", "A2")
    _read_fixture(monkeypatch, {
        "commandes_achats": [second, first],
        "lignes_achats": [line1, line2],
    })
    trend = service.get_kpis_achats(START, END)["evolution_prix"]
    assert trend["prix_unitaire_dzd"].tolist() == [1200, 1500] or sorted(
        trend["prix_unitaire_dzd"].tolist()) == [1200, 1500]
    assert set(trend["unite_cond"]) == {"KG"}


@pytest.mark.parametrize("price", [None, "abc", float("nan"), float("inf"), -1])
def test_purchase_invalid_price_never_replaced_by_zero(monkeypatch, price):
    header, line = _purchase(price if isinstance(price, (int, float)) else 0,
                             1, "DZD", "2026-11-02", "A1")
    line["prix_unitaire"] = price
    _read_fixture(monkeypatch, {"commandes_achats": [header],
                                "lignes_achats": [line]})
    with pytest.raises(DataReadError):
        service.get_kpis_achats(START, END)


def test_purchase_missing_exchange_rate_does_not_draw_noncomparable_price(monkeypatch):
    header, line = _purchase(15, 1, "EUR", "2026-11-02", "A1")
    header.pop("taux_change")
    _read_fixture(monkeypatch, {"commandes_achats": [header],
                                "lignes_achats": [line]})
    assert service.get_kpis_achats(START, END)["evolution_prix"].empty


def test_production_cohort_and_qc_use_distinct_denominators(monkeypatch):
    _read_fixture(monkeypatch, {
        "ordres_fabrication": [
            {"of_id": "O1", "date_planification": "2026-11-01", "statut": "TERMINE"},
            {"of_id": "O2", "date_planification": "2026-11-01", "statut": "EN_COURS"},
            {"of_id": "O3", "date_planification": "2026-11-03", "statut": "PLANIFIE"},
        ],
        "controle_qualite": [
            {"qc_id": "Q1", "date": "2026-11-03", "conforme": "NON"},
            {"qc_id": "Q2", "date": "2026-11-03", "conforme": "OUI"},
        ],
    })
    kpi = service.get_kpis_production(START, END)
    assert kpi["total_ofs"] == 3 and kpi["of_termines"] == 1
    assert kpi["nb_controles"] == 2 and kpi["nb_rejets"] == 1
    assert round(kpi["taux_cloture"], 2) == 33.33
    assert kpi["taux_rejet"] == 50
    assert kpi["evolution_of"]["OF planifiés"].tolist() == [2, 1]


def test_production_cq_with_no_planned_of_is_still_counted(monkeypatch):
    _read_fixture(monkeypatch, {
        "ordres_fabrication": [],
        "controle_qualite": [{"qc_id": "Q", "date": "2026-11-05", "conforme": "NON"}],
    })
    result = service.get_kpis_production(START, END)
    assert result["total_ofs"] == 0
    assert result["nb_controles"] == 1 and result["taux_rejet"] == 100
    assert views._rate_or_na(result["taux_cloture"], result["total_ofs"]) == "N/D"


def test_invalid_control_status_fails_closed(monkeypatch):
    _read_fixture(monkeypatch, {
        "ordres_fabrication": [],
        "controle_qualite": [{"qc_id": "Q", "date": "2026-11-05",
                              "conforme": "INCONNU"}],
    })
    with pytest.raises(DataReadError, match="Conformité CQ inconnue"):
        service.get_kpis_production(START, END)


def test_cash_flow_trend_only_validated_payments_in_date_range(monkeypatch):
    bank = {"compte_id": "B", "nom_compte": "Banque", "type_compte": "Banque",
            "solde_initial": 100}
    def payment(key, day, kind, amount, allocated, status="VALIDE"):
        return {"reglement_id": key, "statut": status, "date_reglement": day,
                "compte_id": "B", "type_flux": kind, "montant_total": amount,
                "montant_alloue": allocated}
    _read_fixture(monkeypatch, {
        "comptes": [bank],
        "reglements": [
            payment("R1", "2026-11-03", "ENCAISSEMENT", 100, 20),
            payment("R2", "2026-11-03", "DECAISSEMENT", 40, 0),
            payment("R3", "2026-11-04", "ENCAISSEMENT", 30, 30),
            payment("R4", "2026-11-05", "ENCAISSEMENT", 999, 0, "BROUILLON"),
            payment("R5", "2026-10-01", "ENCAISSEMENT", 15, 15),
        ],
    })
    kpi = service.get_kpis_finance(START, END)
    assert kpi["flux_entrants"] == 130 and kpi["flux_sortants"] == 40
    assert kpi["flux_net"] == 90
    assert kpi["encaissements_non_alloues"] == 80
    assert kpi["taux_lettrage"] == pytest.approx(50 / 130 * 100)
    trend = kpi["evolution_flux"]
    assert trend["Encaissements (DZD)"].tolist() == [100, 30]
    assert trend["Décaissements (DZD)"].tolist() == [40, 0]


def test_zero_encaissement_not_an_allocation_success(monkeypatch):
    _read_fixture(monkeypatch, {"comptes": [], "reglements": []})
    kpi = service.get_kpis_finance(START, END)
    assert kpi["evolution_flux"].empty
    assert views._rate_or_na(kpi["taux_lettrage"], kpi["flux_entrants"]) == "N/D"


def test_expired_and_upcoming_lots_distinct_from_undated(monkeypatch):
    _read_fixture(monkeypatch, {
        "lots": [
            {"lot_id": "L1", "quantite_restante": 1, "date_peremption": "2026-11-02"},
            {"lot_id": "L2", "quantite_restante": 1, "date_peremption": "2026-11-05"},
            {"lot_id": "L3", "quantite_restante": 1, "date_peremption": "2026-11-20"},
            {"lot_id": "L4", "quantite_restante": 1, "date_peremption": None},
        ],
    })
    kpi = service.get_kpis_stocks(30)
    assert kpi["lots_perimes"] == 1 and kpi["lots_a_echeance"] == 2
    assert kpi["lots_sans_date"] == 1


def test_ratio_nd_and_waterfall_are_pure_local_visuals():
    assert views._rate_or_na(0, 0) == "N/D"
    assert views._rate_or_na(0, 9) == "0.0 %"
    rendered = []
    dashboard = SimpleNamespace(plotly_chart=lambda fig, **kw: rendered.append(fig))
    pnl = {"ca_ht": 1200, "cogs": 600, "opex_fournisseurs": 250,
           "opex_salaires": 150, "ebitda": 200}
    views._show_management_waterfall(dashboard, pnl)
    assert len(rendered) == 1
    waterfall = rendered[0].data[0]
    assert waterfall.type == "waterfall"
    assert list(waterfall.measure) == ["absolute", "relative", "relative",
                                     "relative", "total"]
    assert list(waterfall.y) == [1200, -600, -250, -150, 0]
    # Un total Plotly est y=0 techniquement, mais doit montrer 200 DZD
    # au survol ; les montants négatifs restent signés.
    assert list(waterfall.customdata) == [1200, -600, -250, -150, 200]
    assert "%{customdata:,.2f} DZD" in waterfall.hovertemplate


def test_provenance_detects_demo_and_sim_without_removing_rows(monkeypatch):
    dataset = {
        "factures": [{"facture_id": "DEMO26_F1"},
                     {"facture_id": "FACTURE-REAL"}],
        "reglements": [{"reglement_id": "SIM26_PAY"}],
        "ordres_fabrication": [{"of_id": "OF-REAL"}],
        "commandes_achats": [{"commande_achat_id": "DEMO26_C1"}],
        "pipeline": [{"opportunite_id": "OP-REAL"}],
        "employes": [{"employe_id": "SIM-RH-01"}],
    }
    _read_fixture(monkeypatch, dataset)
    result = service.get_dashboard_data_provenance()
    assert result["marked"] == 4
    assert len(result["sources"]) == 6
    assert result["sources"][0] == {
        "Source": "Factures", "Références DEMO/SIM": 1, "Total": 2,
    }
    # Aucun document n'est modifié ou supprimé par le diagnostic.
    assert len(dataset["factures"]) == 2


def test_provenance_unknown_id_fails_instead_of_false_clean(monkeypatch):
    _read_fixture(monkeypatch, {"factures": [{"statut": "VALIDE"}]})
    with pytest.raises(DataReadError, match="provenance"):
        service.get_dashboard_data_provenance()


def test_provenance_has_no_false_demo_if_real_ids(monkeypatch):
    _read_fixture(monkeypatch, {
        "factures": [{"facture_id": "FAC-100"}],
        "reglements": [{"reglement_id": "REG-100"}],
    })
    assert service.get_dashboard_data_provenance()["marked"] == 0
