"""Tests du pont fiscal en prévalidation, exemples de taux fictifs."""
from datetime import date
from decimal import Decimal
import pytest

from core.liaison_tva_sku import taux_par_ligne
from core.classification_fiscale import ClassificationIndisponible
from core.fiscalite_facturation import FiscaliteNonDisponible


def classification(category="NORMAL", status="VALIDEE"):
    return {
        "sku_id": "SKU-X", "date_effet": "2026-01-01", "date_fin": None,
        "categorie_tva": category,
        "code_parametre": {"NORMAL": "TVA_TAUX_NORMAL",
                           "REDUIT": "TVA_TAUX_REDUIT"}.get(category),
        "statut": status, "source_juridique": "SOURCE-TEST",
        "justification": "TEST", "valide_par": "TEST",
        "date_verification": "2026-01-02", "date_validation": "2026-01-03",
    }


def param(code="TVA_TAUX_NORMAL", rate="0.17", status="en_vigueur"):
    return {
        "code": code, "valeur": rate, "unite": "fraction",
        "statut_juridique": status, "niveau_confiance": "CONFIRMEE",
        "source": "SOURCE-TEST", "date_effet": "2026-01-01",
        "date_fin": None, "date_verification": "2026-01-02",
    }


def test_taux_par_sku_qualifie():
    result = taux_par_ligne([{"sku_id": "SKU-X"}], date(2026, 2, 1),
                            [classification()], [param()])
    assert result[0]["taux_tva"] == Decimal("0.17")
    assert result[0]["justificatif_taux"]["source"] == "SOURCE-TEST"


def test_taux_non_confirme_refuse():
    with pytest.raises(FiscaliteNonDisponible):
        taux_par_ligne([{"sku_id": "SKU-X"}], date(2026, 2, 1),
                       [classification()], [param(status="a_confirmer")])


def test_classification_non_validee_refusee():
    with pytest.raises(ClassificationIndisponible):
        taux_par_ligne([{"sku_id": "SKU-X"}], date(2026, 2, 1),
                       [classification(status="A_VALIDER")], [param()])


def test_exoneration_non_traitee_refusee():
    with pytest.raises(ClassificationIndisponible, match="Exonération"):
        taux_par_ligne([{"sku_id": "SKU-X"}], date(2026, 2, 1),
                       [classification(category="EXONERE")], [param()])


def test_parametre_inexistant_refuse():
    with pytest.raises(FiscaliteNonDisponible):
        taux_par_ligne([{"sku_id": "SKU-X"}], date(2026, 2, 1),
                       [classification(category="REDUIT")], [param()])
