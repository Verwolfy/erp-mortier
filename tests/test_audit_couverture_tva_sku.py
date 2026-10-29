"""Diagnostic TVA en lecture seule : données de test fictives."""
from datetime import date

import pytest

from core.audit_couverture_tva_sku import auditer_couverture_tva


def classification(sku="SKU-A"):
    return {
        "sku_id": sku, "date_effet": "2026-01-01", "date_fin": None,
        "statut": "VALIDEE", "categorie_tva": "NORMAL",
        "code_parametre": "TVA_TAUX_NORMAL",
        "source_juridique": "FICTIVE", "justification": "TEST",
        "valide_par": "TEST", "date_verification": "2026-01-02",
        "date_validation": "2026-01-03",
    }


def parametre():
    return {
        "code": "TVA_TAUX_NORMAL", "valeur": "0.17", "unite": "fraction",
        "statut_juridique": "en_vigueur", "niveau_confiance": "CONFIRMEE",
        "source": "FICTIVE", "date_effet": "2026-01-01",
        "date_fin": None, "date_verification": "2026-01-02",
    }


def test_catalogue_partiellement_qualifie():
    result = auditer_couverture_tva(
        ["SKU-A", "SKU-B"], date(2026, 2, 1),
        [classification()], [parametre()],
    )
    assert result["sku_actifs"] == 2
    assert result["sku_prequalifies"] == 1
    assert result["prequalification_catalogue_complete"] is False
    assert result["autorise_activation_facturation"] is False
    assert result["resultats"][0]["prequalifie"] is True
    assert result["resultats"][1]["blocage"]


def test_catalogue_qualifie_ne_declenche_jamais_activation():
    result = auditer_couverture_tva(
        ["SKU-A"], date(2026, 2, 1), [classification()], [parametre()]
    )
    assert result["prequalification_catalogue_complete"] is True
    assert result["autorise_activation_facturation"] is False


def test_aucune_classification_mais_sku_actifs():
    result = auditer_couverture_tva(
        ["SKU-A", "SKU-B"], date(2026, 2, 1), [], [parametre()]
    )
    assert result["sku_prequalifies"] == 0
    assert all(x["prequalifie"] is False for x in result["resultats"])


def test_catalogue_vide_n_est_pas_pret():
    result = auditer_couverture_tva([], date(2026, 2, 1), [], [])
    assert result["prequalification_catalogue_complete"] is False
    assert result["autorise_activation_facturation"] is False


@pytest.mark.parametrize("sku", [["SKU-A", "SKU-A"], [None], [{"sku_id": "SKU-A"}], [""]])
def test_skus_malformes_refuses(sku):
    with pytest.raises(ValueError, match="Liste SKU"):
        auditer_couverture_tva(sku, date(2026, 2, 1), [], [])


def test_parametre_non_confirme_est_un_blocage():
    p = parametre()
    p["niveau_confiance"] = "A_CONFIRMER"
    result = auditer_couverture_tva(
        ["SKU-A"], date(2026, 2, 1), [classification()], [p]
    )
    assert result["sku_prequalifies"] == 0
    assert result["resultats"][0]["blocage"]
