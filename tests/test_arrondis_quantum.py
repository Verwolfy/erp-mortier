"""Régression sur les unités de calcul paramétrables, avec taux fictifs."""
from decimal import Decimal

import pytest

from core.arrondis import ArrondiNonDisponible, arrondir_multiple
from core.baremes import BaremeIndisponible, calculer_bareme_progressif
from core.reglementation import RegleIndisponible, calculer_pourcentage


def regle_taux():
    return {
        "code": "TEST",
        "valeur": "0.125",
        "date_effet": "2026-01-01",
        "date_fin": None,
        "date_verification": "2026-01-02",
        "statut_juridique": "en_vigueur",
        "niveau_confiance": "CONFIRMEE",
        "source": "EXEMPLE_NON_JURIDIQUE",
    }


def regle_bareme():
    return {
        "code": "TEST_TRANCHE",
        "type_regle": "progressif",
        "date_effet": "2026-01-01",
        "date_fin": None,
        "date_verification": "2026-01-02",
        "statut_juridique": "en_vigueur",
        "niveau_confiance": "CONFIRMEE",
        "source": "EXEMPLE_NON_JURIDIQUE",
        "donnees": {"tranches": [
            {"jusqua": "100", "taux": "0"},
            {"jusqua": None, "taux": "0.1"},
        ]},
    }


@pytest.mark.parametrize("value,step,expected", [
    ("0.125", "0.01", "0.13"),
    ("0.125", "0.05", "0.15"),
    ("0.124", "0.05", "0.10"),
    ("2.5", "5", "5"),
    ("7.5", "5.00", "10.00"),
    ("0", "0.05", "0.00"),
    ("0.000", "0.001", "0.000"),
])
def test_arrondi_au_multiple_exact(value, step, expected):
    assert str(arrondir_multiple(Decimal(value), Decimal(step))) == expected


def test_calcul_taux_au_quantum_005():
    result = calculer_pourcentage(
        "1.00", [regle_taux()], "TEST", "2026-10-28", unite_arrondi="0.05",
    )
    assert result["montant"] == "0.15"


def test_bareme_au_quantum_005():
    result = calculer_bareme_progressif(
        "150.25", regle_bareme(), "2026-10-28",
        code="TEST_TRANCHE", unite_arrondi="0.05",
    )
    assert result["montant"] == "5.05"


@pytest.mark.parametrize("step", [
    "0", "-1", "NaN", "Infinity", "0.0000000001", "10000000000"
])
def test_quantum_refuse_dans_les_deux_moteurs(step):
    with pytest.raises(RegleIndisponible):
        calculer_pourcentage("1", [regle_taux()], "TEST", "2026-10-28", unite_arrondi=step)
    with pytest.raises(BaremeIndisponible):
        calculer_bareme_progressif(
            "150", regle_bareme(), "2026-10-28",
            code="TEST_TRANCHE", unite_arrondi=step,
        )


@pytest.mark.parametrize("value,step", [
    (Decimal("NaN"), Decimal("0.01")),
    (Decimal("Infinity"), Decimal("0.01")),
    (Decimal("1"), Decimal("0")),
    (Decimal("1"), Decimal("-0.01")),
])
def test_utilitaire_refuse_les_valeurs_non_finies(value, step):
    with pytest.raises(ArrondiNonDisponible):
        arrondir_multiple(value, step)
