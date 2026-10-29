"""Contrôles du panier fiscal, valeurs et sources exclusivement fictives."""
from datetime import date

import pytest

from core.classification_fiscale import ClassificationIndisponible
from core.precontrole_panier_fiscal import verifier_panier_fiscal


def classement(sku):
    return {
        "sku_id": sku, "date_effet": "2026-01-01", "date_fin": None,
        "statut": "VALIDEE", "categorie_tva": "NORMAL",
        "code_parametre": "TVA_TAUX_NORMAL",
        "source_juridique": "SOURCE-FICTIVE-TEST",
        "justification": "TEST", "valide_par": "TEST",
        "date_verification": "2026-01-02",
        "date_validation": "2026-01-03",
    }


def test_toutes_les_lignes_sont_qualifiees():
    a, b = classement("SKU-A"), classement("SKU-B")
    resultats = verifier_panier_fiscal(
        [{"sku_id": "SKU-A"}, {"sku_id": "SKU-B"}],
        date(2026, 2, 1), [a, b],
    )
    assert resultats == [a, b]


def test_un_seul_sku_non_qualifie_bloque_tout_le_panier():
    with pytest.raises(ClassificationIndisponible):
        verifier_panier_fiscal(
            [{"sku_id": "SKU-A"}, {"sku_id": "SKU-INCONNU"}],
            date(2026, 2, 1), [classement("SKU-A")],
        )


def test_classification_non_validee_bloque_tout():
    a = classement("SKU-A")
    a["statut"] = "A_VALIDER"
    with pytest.raises(ClassificationIndisponible):
        verifier_panier_fiscal([{"sku_id": "SKU-A"}], date(2026, 2, 1), [a])


@pytest.mark.parametrize("lignes", [[], [{}], [{"sku_id": ""}], ["invalide"]])
def test_panier_invalide_refuse(lignes):
    with pytest.raises(ClassificationIndisponible):
        verifier_panier_fiscal(lignes, date(2026, 2, 1), [])


def test_trop_de_lignes_refuse():
    with pytest.raises(ClassificationIndisponible, match="500"):
        verifier_panier_fiscal(
            [{"sku_id": "SKU-A"}] * 501, date(2026, 2, 1), [classement("SKU-A")]
        )


def test_referentiel_invalide_refuse():
    with pytest.raises(ClassificationIndisponible, match="Référentiel"):
        verifier_panier_fiscal([{"sku_id": "SKU-A"}], date(2026, 2, 1), None)


def test_panier_reutilise_referentiel_sans_altération():
    a, b = classement("SKU-A"), classement("SKU-B")
    referentiel = [a, b]
    verifier_panier_fiscal(
        [{"sku_id": "SKU-A"}, {"sku_id": "SKU-B"}],
        date(2026, 2, 1), referentiel,
    )
    assert referentiel == [a, b]
