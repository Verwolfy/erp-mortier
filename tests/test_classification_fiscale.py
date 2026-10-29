"""Contrats purs de classification fiscale SKU, valeurs fictives."""
from datetime import date
import pytest
from core.classification_fiscale import ClassificationIndisponible, selectionner_classification


def row(start="2026-01-01", end=None, **kw):
    return {"sku_id": "SKU-TEST", "date_effet": start, "date_fin": end,
            "statut_juridique": "en_vigueur", "niveau_confiance": "CONFIRMEE",
            "source": "SOURCE-FICTIVE-TEST", **kw}


def test_classification_datee_exacte():
    a = row(start="2025-01-01", end="2025-12-31")
    b = row(start="2026-01-01")
    assert selectionner_classification("SKU-TEST", date(2025, 12, 31), [a, b]) is a
    assert selectionner_classification("SKU-TEST", date(2026, 1, 1), [a, b]) is b


def test_ambiguite_interdite():
    with pytest.raises(ClassificationIndisponible, match="ambiguë"):
        selectionner_classification("SKU-TEST", date(2026, 2, 1), [row(), row()])


def test_absence_interdite():
    with pytest.raises(ClassificationIndisponible):
        selectionner_classification("SKU-INCONNU", date(2026, 2, 1), [row()])


@pytest.mark.parametrize("field,value", [
    ("statut_juridique", "a_confirmer"),
    ("niveau_confiance", "NON_VERIFIEE"),
])
def test_non_confirme_refuse(field, value):
    item = row()
    item[field] = value
    with pytest.raises(ClassificationIndisponible):
        selectionner_classification("SKU-TEST", date(2026, 2, 1), [item])


def test_source_absente_interdite():
    item = row()
    item["source"] = ""
    with pytest.raises(ClassificationIndisponible, match="Source"):
        selectionner_classification("SKU-TEST", date(2026, 2, 1), [item])


def test_classification_bdd_reelle_validee():
    from core.classification_fiscale import selectionner_classification_bdd
    bdd = {
        "sku_id": "SKU-TEST", "date_effet": date(2026, 1, 1),
        "date_fin": None, "statut": "VALIDEE", "categorie_tva": "NORMAL",
        "code_parametre": "TVA_TAUX_NORMAL",
        "source_juridique": "SOURCE-FICTIVE", "justification": "TEST",
        "valide_par": "TEST", "date_verification": date(2026, 1, 2),
        "date_validation": date(2026, 1, 3),
    }
    assert selectionner_classification_bdd("SKU-TEST", date(2026, 2, 1), [bdd]) is bdd


def test_classification_bdd_non_validee_refusee():
    from core.classification_fiscale import selectionner_classification_bdd
    bdd = {
        "sku_id": "SKU-TEST", "date_effet": "2026-01-01",
        "date_fin": None, "statut": "A_VALIDER", "categorie_tva": "NORMAL",
        "code_parametre": "TVA_TAUX_NORMAL",
    }
    with pytest.raises(ClassificationIndisponible):
        selectionner_classification_bdd("SKU-TEST", date(2026, 2, 1), [bdd])


def test_classification_bdd_incoherente_refusee():
    from core.classification_fiscale import selectionner_classification_bdd
    bdd = {
        "sku_id": "SKU-TEST", "date_effet": "2026-01-01",
        "date_fin": None, "statut": "VALIDEE", "categorie_tva": "REDUIT",
        "code_parametre": "TVA_TAUX_NORMAL",
        "source_juridique": "SOURCE-FICTIVE", "justification": "TEST",
        "valide_par": "TEST", "date_verification": "2026-01-02",
        "date_validation": "2026-01-03",
    }
    with pytest.raises(ClassificationIndisponible, match="incohérents"):
        selectionner_classification_bdd("SKU-TEST", date(2026, 2, 1), [bdd])



def test_classification_bdd_validation_avant_verification_refusee():
    from core.classification_fiscale import selectionner_classification_bdd
    bdd = {
        "sku_id": "SKU-TEST", "date_effet": "2026-01-01",
        "date_fin": None, "statut": "VALIDEE", "categorie_tva": "NORMAL",
        "code_parametre": "TVA_TAUX_NORMAL",
        "source_juridique": "SOURCE-FICTIVE", "justification": "TEST",
        "valide_par": "TEST", "date_verification": "2026-01-04",
        "date_validation": "2026-01-03",
    }
    with pytest.raises(ClassificationIndisponible, match="antérieure"):
        selectionner_classification_bdd("SKU-TEST", date(2026, 2, 1), [bdd])


def test_classification_bdd_date_validation_invalide_refusee():
    from core.classification_fiscale import selectionner_classification_bdd
    bdd = {
        "sku_id": "SKU-TEST", "date_effet": "2026-01-01",
        "date_fin": None, "statut": "VALIDEE", "categorie_tva": "NORMAL",
        "code_parametre": "TVA_TAUX_NORMAL",
        "source_juridique": "SOURCE-FICTIVE", "justification": "TEST",
        "valide_par": "TEST", "date_verification": "date-invalide",
        "date_validation": "2026-01-03",
    }
    with pytest.raises(ClassificationIndisponible, match="Date de validation invalide"):
        selectionner_classification_bdd("SKU-TEST", date(2026, 2, 1), [bdd])


def test_classification_validee_apres_operation_refusee():
    from core.classification_fiscale import selectionner_classification_bdd
    item = {
        "sku_id": "SKU-TEST", "date_effet": "2026-01-01",
        "date_fin": None, "statut": "VALIDEE", "categorie_tva": "NORMAL",
        "code_parametre": "TVA_TAUX_NORMAL", "source_juridique": "TEST",
        "justification": "TEST", "valide_par": "TEST",
        "date_verification": "2026-02-01", "date_validation": "2026-02-02",
    }
    with pytest.raises(ClassificationIndisponible, match="après la date"):
        selectionner_classification_bdd("SKU-TEST", date(2026, 1, 15), [item])


def test_classification_bdd_fin_avant_debut_refusee():
    from core.classification_fiscale import selectionner_classification_bdd
    item = {
        "sku_id": "SKU-TEST", "date_effet": "2026-02-01",
        "date_fin": "2026-01-01", "statut": "VALIDEE",
        "categorie_tva": "NORMAL", "code_parametre": "TVA_TAUX_NORMAL",
        "source_juridique": "TEST", "justification": "TEST",
        "valide_par": "TEST", "date_verification": "2026-01-02",
        "date_validation": "2026-01-03",
    }
    with pytest.raises(ClassificationIndisponible, match="Période fiscale"):
        selectionner_classification_bdd("SKU-TEST", date(2026, 2, 3), [item])


def _classification_validee_bdd(sku, debut, fin=None, validation="2026-01-03"):
    return {
        "sku_id": sku, "date_effet": debut, "date_fin": fin,
        "statut": "VALIDEE", "categorie_tva": "NORMAL",
        "code_parametre": "TVA_TAUX_NORMAL", "source_juridique": "SOURCE-FICTIVE",
        "justification": "TEST", "valide_par": "TEST",
        "date_verification": "2026-01-02", "date_validation": validation,
    }


def test_bdd_une_version_future_ne_bloque_pas_l_historique():
    from core.classification_fiscale import selectionner_classification_bdd
    ancienne = _classification_validee_bdd("SKU-TEST", "2026-01-01", "2026-06-30")
    future = _classification_validee_bdd("SKU-TEST", "2026-07-01", validation="2026-07-03")
    assert selectionner_classification_bdd(
        "SKU-TEST", date(2026, 3, 1), [future, ancienne]
    ) is ancienne


def test_bdd_ancienne_version_expiree_n_empeche_pas_la_version_valide():
    from core.classification_fiscale import selectionner_classification_bdd
    expiree = _classification_validee_bdd("SKU-TEST", "2026-01-01", "2026-06-30")
    expiree["source_juridique"] = ""
    courante = _classification_validee_bdd("SKU-TEST", "2026-07-01", validation="2026-07-03")
    assert selectionner_classification_bdd(
        "SKU-TEST", date(2026, 8, 1), [expiree, courante]
    ) is courante


def test_bdd_versions_chevauchantes_refusees():
    from core.classification_fiscale import selectionner_classification_bdd
    a = _classification_validee_bdd("SKU-TEST", "2026-01-01", "2026-09-30")
    b = _classification_validee_bdd("SKU-TEST", "2026-06-01", validation="2026-06-03")
    with pytest.raises(ClassificationIndisponible, match="ambiguë"):
        selectionner_classification_bdd("SKU-TEST", date(2026, 8, 1), [a, b])


def test_bdd_version_future_seule_refusee():
    from core.classification_fiscale import selectionner_classification_bdd
    future = _classification_validee_bdd("SKU-TEST", "2026-07-01", validation="2026-07-03")
    with pytest.raises(ClassificationIndisponible, match="absente"):
        selectionner_classification_bdd("SKU-TEST", date(2026, 3, 1), [future])
