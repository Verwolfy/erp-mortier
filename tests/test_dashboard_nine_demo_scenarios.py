"""Contrats des neuf agrégations du Dashboard sur un jeu fictif entièrement local.

Aucune connexion Supabase, aucune donnée réelle, aucun export fiscal.
Les constantes correspondent au scénario DEMO26 chargé le 2026-11-05.
"""
from datetime import datetime

import pandas as pd
import pytest

from modules.dashboards import service


@pytest.fixture
def demo(monkeypatch):
    table = {
        "factures": [
            {"facture_id": "DEMO26_FAC1", "type_facture": "FactureClient",
             "statut": "VALIDE", "date": "2026-11-03", "date_echeance": "2026-11-30",
             "client_id": "DEMO26_CLI1", "montant_ht": 16000, "montant_ttc": 19040,
             "montant_paye": 3000, "montant_timbre": 0},
            {"facture_id": "DEMO26_FAC2", "type_facture": "FactureClient",
             "statut": "VALIDE", "date": "2026-09-01", "date_echeance": "2026-09-30",
             "client_id": "DEMO26_CLI2", "montant_ht": 10000, "montant_ttc": 11900,
             "montant_paye": 0, "montant_timbre": 0},
        ],
        "lignes_facture": [
            {"facture_id": "DEMO26_FAC1", "sku_id": "DEMO26_SKU1", "quantite": 10},
            {"facture_id": "DEMO26_FAC2", "sku_id": "DEMO26_SKU2", "quantite": 4},
        ],
        "stock_actuel_pf": [
            {"sku_id": "DEMO26_SKU1", "quantite_disponible": 180, "cout_revient": 1000},
            {"sku_id": "DEMO26_SKU2", "quantite_disponible": 60, "cout_revient": 1500},
        ],
        "stock_actuel": [
            {"mp_id": "DEMO26_MP1", "quantite_disponible": 100, "cmp_actuel": 80},
            {"mp_id": "DEMO26_MP2", "quantite_disponible": 220, "cmp_actuel": 250},
        ],
        "matieres_premieres": [
            {"mp_id": "DEMO26_MP1", "stock_mini": 500},
            {"mp_id": "DEMO26_MP2", "stock_mini": 80},
        ],
        "lots": [
            {"lot_id": "DEMO26_LOT1", "quantite_restante": 100, "date_peremption": "2026-11-20"},
            {"lot_id": "DEMO26_LOT2", "quantite_restante": 180, "date_peremption": "2027-10-20"},
        ],
        "comptes": [
            {"compte_id": "DEMO26_BANK", "nom_compte": "[FICTIF] Banque",
             "type_compte": "Banque", "solde_initial": 1000000},
            {"compte_id": "DEMO26_CASH", "nom_compte": "[FICTIF] Caisse",
             "type_compte": "Caisse", "solde_initial": 25000},
        ],
        "reglements": [
            {"reglement_id": "DEMO26_RG1", "statut": "VALIDE",
             "date_reglement": "2026-11-04", "compte_id": "DEMO26_BANK",
             "type_flux": "ENCAISSEMENT", "partenaire_id": "DEMO26_CLI1",
             "montant_total": 3000, "montant_alloue": 3000},
            {"reglement_id": "DEMO26_RG2", "statut": "VALIDE",
             "date_reglement": "2026-11-04", "compte_id": "DEMO26_BANK",
             "type_flux": "DECAISSEMENT", "partenaire_id": "DEMO26_FOU2",
             "montant_total": 5000, "montant_alloue": 0},
        ],
        "fournisseurs": [
            {"fournisseur_id": "DEMO26_FOU1", "categorie": "MATIERES"},
            {"fournisseur_id": "DEMO26_FOU2", "categorie": "SERVICES OPEX"},
        ],
        "fiches_de_paie": [
            {"fiche_paie_id": "DEMO26_FP1", "mois": 11, "annee": 2026,
             "net_a_payer": 50000, "statut_paiement": "BROUILLON"},
        ],
        "commandes_achats": [
            {"commande_achat_id": "DEMO26_CA1", "date_commande": "2026-11-02",
             "date_voulue": "2026-11-15", "statut": "EN_ATTENTE",
             "fournisseur_id": "DEMO26_FOU1", "montant_total_local": 80000},
            {"commande_achat_id": "DEMO26_CA2", "date_commande": "2026-09-20",
             "date_voulue": "2026-10-01", "statut": "EN_ATTENTE",
             "fournisseur_id": "DEMO26_FOU2", "montant_total_local": 5000},
        ],
        "lignes_achats": [
            {"commande_achat_id": "DEMO26_CA1", "mp_id": "DEMO26_MP1",
             "prix_unitaire": 80},
        ],
        "ordres_fabrication": [
            {"of_id": "DEMO26_OF1", "statut": "EN_COURS", "date_planification": "2026-11-02"},
            {"of_id": "DEMO26_OF2", "statut": "PLANIFIE", "date_planification": "2026-11-04"},
        ],
        "controle_qualite": [
            {"qc_id": "DEMO26_QC1", "date": "2026-11-04", "conforme": "NON"},
        ],
        "pipeline": [
            {"opportunite_id": "DEMO26_OP1", "statut": "En Négociation",
             "valeur_estimee": 500000, "probabilite_pct": 60,
             "date_creation": "2026-11-02", "commercial_id": "DEMO26_EMP2"},
            {"opportunite_id": "DEMO26_OP2", "statut": "Gagné",
             "valeur_estimee": 200000, "probabilite_pct": 100,
             "date_creation": "2026-11-03", "commercial_id": "DEMO26_EMP2"},
            {"opportunite_id": "DEMO26_OP3", "statut": "Perdu",
             "valeur_estimee": 85000, "probabilite_pct": 0,
             "date_creation": "2026-11-03", "commercial_id": "DEMO26_EMP2"},
        ],
        "employes": [
            {"employe_id": "DEMO26_EMP1", "actif": "OUI", "service": "Production"},
            {"employe_id": "DEMO26_EMP2", "actif": "OUI", "service": "Ventes"},
        ],
        "demandes_conges": [
            {"demande_conge_id": "DEMO26_CONGE1", "statut": "EN_ATTENTE"},
        ],
    }
    monkeypatch.setattr(service, "fetch_data", lambda name: [dict(x) for x in table.get(name, [])])

    def by_date(name, column, start, end):
        return [dict(x) for x in table.get(name, [])
                if x.get(column) is not None and start <= x[column] <= end]

    monkeypatch.setattr(service, "fetch_data_by_date_range", by_date)
    monkeypatch.setattr(service, "get_local_now", lambda: datetime(2026, 11, 5, 12, 0))
    return table


START = pd.Timestamp("2026-11-01")
END = pd.Timestamp("2026-11-30")


def test_direction_demo(demo):
    k = service.get_kpis_direction()
    assert k["ca_mois"] == 16000
    assert k["tresorerie"] == 1023000
    assert k["impayes_30j"] == 11900
    assert k["alertes_stock"] == 1


def test_rentabilite_demo(demo):
    k = service.get_kpis_pnl(START, END)
    assert (k["ca_ht"], k["cogs"], k["opex_fournisseurs"],
            k["opex_salaires"], k["ebitda"]) == (16000, 10000, 5000, 50000, -49000)


def test_ventes_demo(demo):
    k = service.get_kpis_ventes(START, END)
    assert k["nb_factures"] == 1
    assert k["ca_ht"] == 16000
    assert k["balance_agee"]["31 à 60 jours"] == 11900
    assert k["balance_agee"]["1 à 30 jours"] == 0
    assert k["balance_agee"]["+ de 60 jrs"] == 0


def test_achats_demo(demo):
    k = service.get_kpis_achats(START, END)
    assert k["montant_total"] == 80000
    assert k["commandes_retard"] == 1


def test_stocks_demo(demo):
    k = service.get_kpis_stocks(30)
    assert (k["valeur_mp"], k["valeur_pf"], k["sous_seuil"]) == (63000, 270000, 1)
    assert len(k["lots_expirants"]) == 1


def test_production_demo(demo):
    k = service.get_kpis_production(START, END)
    assert k["total_ofs"] == 2
    assert k["taux_rejet"] == 100


def test_crm_demo(demo):
    k = service.get_kpis_crm(START, END)
    assert k["pipeline_pondere"] == 300000
    assert k["taux_conversion"] == 50


def test_rh_demo(demo):
    k = service.get_kpis_rh(START, END)
    assert k["effectif_actif"] == 2
    assert k["conges_attente"] == 1


def test_finance_demo(demo):
    k = service.get_kpis_finance(START, END)
    assert k["flux_entrants"] == 3000
    assert k["flux_sortants"] == 5000
    assert k["taux_lettrage"] == 100


def test_direction_et_stocks_avec_107_seuils_non_configures(demo):
    """Régression de la panne constatée sur la base, sans inventer les 107 seuils."""
    for i in range(107):
        demo["matieres_premieres"].append({"mp_id": f"MP_NON_SEUIL_{i}", "stock_mini": None})
        demo["stock_actuel"].append({"mp_id": f"MP_NON_SEUIL_{i}",
                                     "quantite_disponible": 0, "cmp_actuel": None})
    direction = service.get_kpis_direction()
    assert direction["ca_mois"] == 16000
    assert direction["alertes_stock"] == 1
    assert direction["seuils_stock_absents"] == 107
    stocks = service.get_kpis_stocks(30)
    assert stocks["sous_seuil"] == 1
    assert stocks["seuils_stock_absents"] == 107
    assert stocks["valeur_mp"] == 63000
