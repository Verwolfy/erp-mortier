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


def test_parametre_tva_non_confirme_concurrent_bloque_tout():
    valide = param()
    provisoire = param(rate="0.21", status="a_confirmer")
    with pytest.raises(FiscaliteNonDisponible, match="non confirmé"):
        taux_par_ligne(
            [{"sku_id": "SKU-X"}], date(2026, 2, 1),
            [classification()], [valide, provisoire],
        )


def test_parametre_tva_provisoire_futur_ne_bloque_pas_historique():
    valide = param()
    futur = param(rate="0.21", status="a_confirmer")
    futur["date_effet"] = "2027-01-01"
    assert taux_par_ligne(
        [{"sku_id": "SKU-X"}], date(2026, 2, 1),
        [classification()], [futur, valide],
    )[0]["taux_tva"] == Decimal("0.17")


def test_parametre_tva_provisoire_expire_ne_bloque_pas_periode_courante():
    valide = param()
    ancien = param(rate="0.21", status="a_confirmer")
    ancien["date_effet"] = "2025-01-01"
    ancien["date_fin"] = "2025-12-31"
    assert taux_par_ligne(
        [{"sku_id": "SKU-X"}], date(2026, 2, 1),
        [classification()], [ancien, valide],
    )[0]["taux_tva"] == Decimal("0.17")


def test_preuve_classification_complete_et_independante():
    from copy import deepcopy
    cls = classification()
    resultat = taux_par_ligne(
        [{"sku_id": "SKU-X"}], date(2026, 2, 1), [cls], [param()]
    )
    trace = deepcopy(resultat[0]["justificatif_classification"])
    assert trace == {
        "sku_id": "SKU-X",
        "categorie_tva": "NORMAL",
        "code_parametre": "TVA_TAUX_NORMAL",
        "date_effet": "2026-01-01",
        "date_fin": None,
        "source_juridique": "SOURCE-TEST",
        "justification": "TEST",
        "date_verification": "2026-01-02",
        "valide_par": "TEST",
        "date_validation": "2026-01-03",
    }
    cls["source_juridique"] = "MODIFIE"
    cls["justification"] = "MODIFIE"
    assert resultat[0]["justificatif_classification"] == trace


def test_preuve_dates_bdd_normalisees_iso():
    cls = classification()
    cls["date_effet"] = date(2026, 1, 1)
    cls["date_verification"] = date(2026, 1, 2)
    cls["date_validation"] = date(2026, 1, 3)
    cls["date_fin"] = date(2026, 12, 31)
    resultat = taux_par_ligne(
        [{"sku_id": "SKU-X"}], date(2026, 2, 1), [cls], [param()]
    )
    preuve = resultat[0]["justificatif_classification"]
    assert preuve["date_effet"] == "2026-01-01"
    assert preuve["date_fin"] == "2026-12-31"
    assert preuve["date_validation"] == "2026-01-03"
