"""Contrats de simulation TVA par ligne. Taux et sources FICTIFS uniquement."""
from datetime import date
from decimal import Decimal

import pytest

from core.classification_fiscale import ClassificationIndisponible
from core.fiscalite_facturation import FiscaliteNonDisponible
from core.simulation_facture_tva_lignes import simuler_tva_facture_lignes


def classe(sku, categorie):
    return {
        "sku_id": sku, "date_effet": "2026-01-01", "date_fin": None,
        "statut": "VALIDEE", "categorie_tva": categorie,
        "code_parametre": f"TVA_TAUX_{categorie}",
        "source_juridique": "SOURCE-TEST-FICTIVE",
        "justification": "EXEMPLE", "valide_par": "TEST",
        "date_verification": "2026-01-02", "date_validation": "2026-01-03",
    }


def param(code, taux):
    return {
        "code": code, "valeur": taux, "unite": "fraction",
        "statut_juridique": "en_vigueur", "niveau_confiance": "CONFIRMEE",
        "source": "SOURCE-TEST-FICTIVE", "date_effet": "2026-01-01",
        "date_fin": None, "date_verification": "2026-01-02",
    }


def catalogue():
    return (
        [classe("SKU-A", "NORMAL"), classe("SKU-B", "REDUIT")],
        [param("TVA_TAUX_NORMAL", "0.17"), param("TVA_TAUX_REDUIT", "0.09")],
    )


def panier():
    return [
        {"sku_id": "SKU-A", "quantite": "2", "prix_unitaire": "12.345", "remise": "0.01"},
        {"sku_id": "SKU-B", "quantite": "1", "prix_unitaire": "10.055", "remise": "0"},
    ]


def calcul(lignes=None, **kwargs):
    classes, parametres = catalogue()
    return simuler_tva_facture_lignes(
        panier() if lignes is None else lignes,
        date(2026, 2, 1), classes, parametres, **kwargs,
    )


def test_simulation_tva_mixte_par_ligne():
    result = calcul()
    assert [row["montant_ht"] for row in result["lignes"]] == [
        Decimal("24.68"), Decimal("10.06"),
    ]
    assert [row["montant_tva"] for row in result["lignes"]] == [
        Decimal("4.20"), Decimal("0.91"),
    ]
    assert result["montant_ht"] == Decimal("34.74")
    assert result["montant_tva"] == Decimal("5.11")
    assert result["montant_ttc"] == Decimal("39.85")
    assert result["montant_timbre"] == 0
    assert result["simulation_sans_ecriture"] is True
    assert result["autorise_activation_facturation"] is False


def test_une_seule_classification_absente_bloque_facture():
    classes, parametres = catalogue()
    with pytest.raises(ClassificationIndisponible):
        simuler_tva_facture_lignes(panier(), date(2026, 2, 1), classes[:1], parametres)


@pytest.mark.parametrize("kwargs", [
    {"remise_globale": "1.00"}, {"paiement_especes": True},
    {"paiement_especes": "false"}, {"remise_globale": 0.0},
])
def test_options_non_homologuees_refusees(kwargs):
    with pytest.raises(FiscaliteNonDisponible):
        calcul(**kwargs)


@pytest.mark.parametrize("lignes", [
    [], [{"sku_id": "SKU-A", "quantite": "0", "prix_unitaire": "1"}],
    [{"sku_id": "SKU-A", "quantite": "1.5", "prix_unitaire": "1"}],
    [{"sku_id": "SKU-A", "quantite": "1", "prix_unitaire": "5", "remise": "6"}],
    [{"sku_id": "SKU-A", "quantite": 1, "prix_unitaire": 1.0}],
    [{"sku_id": "SKU-A", "quantite": "1", "prix_unitaire": "-1"}],
])
def test_panier_financier_invalide_refuse(lignes):
    with pytest.raises(FiscaliteNonDisponible):
        calcul(lignes)


def test_taux_non_confirme_refuse():
    classes, parametres = catalogue()
    parametres[0]["niveau_confiance"] = "A_CONFIRMER"
    with pytest.raises(FiscaliteNonDisponible):
        simuler_tva_facture_lignes(panier(), date(2026, 2, 1), classes, parametres)


def test_precision_arrondi_centime():
    result = calcul([{"sku_id": "SKU-A", "quantite": "1",
                      "prix_unitaire": "0.005", "remise": "0"}])
    assert result["montant_ht"] == Decimal("0.01")
