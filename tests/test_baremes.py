"""Tests du moteur générique de tranches avec barèmes exclusivement fictifs."""
from decimal import Decimal

import pytest

from core.baremes import (
    BaremeIndisponible, calculer_bareme_progressif,
    calculer_bareme_depuis_registre,
)


def regle(**changements):
    exemple = dict(
        code="TEST_PROGRESSIF", statut_juridique="en_vigueur",
        niveau_confiance="CONFIRMEE", source="SOURCE_FICTIVE_DE_TEST",
        date_verification="2026-01-02", date_effet="2026-01-01",
        date_fin=None, tranches=[
            {"jusqua": "100", "taux": "0"},
            {"jusqua": "200", "taux": "0.10"},
            {"jusqua": None, "taux": "0.20"},
        ],
    )
    exemple.update(changements)
    return exemple


@pytest.mark.parametrize("base,attendu", [
    ("0", "0.00"), ("100", "0.00"), ("150", "5.00"),
    ("200", "10.00"), ("201", "10.20"), ("300", "30.00"),
])
def test_tranches_progressives(base, attendu):
    result = calculer_bareme_progressif(
        base, regle(), "2026-06-30", code="TEST_PROGRESSIF",
    )
    assert result["montant"] == attendu
    assert sum(Decimal(l["montant_non_arrondi"]) for l in result["tranches"]) == Decimal(attendu)


def test_precision_decimal_et_arrondi_unique():
    calc = calculer_bareme_progressif(
        "0.05", regle(tranches=[
            {"jusqua": "0.02", "taux": "0.10"},
            {"jusqua": None, "taux": "0.10"},
        ]), "2026-06-30", code="TEST_PROGRESSIF",
    )
    assert calc["montant"] == "0.01"
    assert calc["tranches"][0]["montant_non_arrondi"] == "0.0020"


@pytest.mark.parametrize("change", [
    {"statut_juridique": "projet"},
    {"statut_juridique": "a_confirmer"},
    {"niveau_confiance": "NON_VERIFIEE"},
    {"source": ""},
    {"date_effet": "2027-01-01"},
    {"date_fin": "2026-02-01"},
    {"date_verification": None},
    {"code": "AUTRE"},
])
def test_refus_regle_non_applicable(change):
    with pytest.raises(BaremeIndisponible):
        calculer_bareme_progressif(
            "150", regle(**change), "2026-06-30", code="TEST_PROGRESSIF",
        )


@pytest.mark.parametrize("liste", [
    [],
    [{"jusqua": "100", "taux": "0.2"}],
    [{"jusqua": None, "taux": "0.2"}, {"jusqua": None, "taux": "0.3"}],
    [{"jusqua": "100", "taux": "0.2"}, {"jusqua": "90", "taux": "0.3"},
     {"jusqua": None, "taux": "0.4"}],
    [{"jusqua": "100", "taux": "-0.1"}, {"jusqua": None, "taux": "0.3"}],
    [{"jusqua": "100", "taux": "1.1"}, {"jusqua": None, "taux": "0.3"}],
])
def test_refus_tranches_invalides(liste):
    with pytest.raises(BaremeIndisponible):
        calculer_bareme_progressif(
            "150", regle(tranches=liste), "2026-06-30", code="TEST_PROGRESSIF",
        )


@pytest.mark.parametrize("base", [
    True, 1.5, "NaN", "Infinity", "-1", "1000000000000000",
])
def test_assiettes_invalides(base):
    with pytest.raises(BaremeIndisponible):
        calculer_bareme_progressif(
            base, regle(), "2026-06-30", code="TEST_PROGRESSIF",
        )


def test_piste_audit():
    resultat = calculer_bareme_progressif(
        "201", regle(), "2026-01-01", code="TEST_PROGRESSIF",
    )
    assert resultat["source"] == "SOURCE_FICTIVE_DE_TEST"
    assert resultat["date_verification"] == "2026-01-02"
    assert resultat["tranches"][1]["assiette_tranche"] == "100"


def test_bareme_depuis_registre_sql_jsonb():
    configuration = regle()
    tranches = configuration.pop("tranches")
    configuration["donnees"] = {"tranches": tranches}
    assert calculer_bareme_progressif(
        "300", configuration, "2026-06-30", code="TEST_PROGRESSIF",
    )["montant"] == "30.00"


def test_bareme_ambigu_refuse():
    configuration = regle(donnees={
        "tranches": [{"jusqua": None, "taux": "1"}],
    })
    with pytest.raises(BaremeIndisponible):
        calculer_bareme_progressif(
            "300", configuration, "2026-06-30", code="TEST_PROGRESSIF",
        )


def test_selection_dans_registre_versionne():
    ancien = regle(date_fin="2026-06-30")
    nouveau = regle(date_effet="2026-07-01")
    ancien["donnees"] = {"tranches": ancien.pop("tranches")}
    nouveau["donnees"] = {"tranches": nouveau.pop("tranches")}
    for date in ("2026-06-30", "2026-07-01"):
        assert calculer_bareme_depuis_registre(
            "300", [ancien, nouveau], date, code="TEST_PROGRESSIF",
        )["montant"] == "30.00"


def test_selection_refuse_chevauchement():
    with pytest.raises(BaremeIndisponible):
        calculer_bareme_depuis_registre(
            "100", [regle(), regle()], "2026-01-01", code="TEST_PROGRESSIF",
        )


def test_selection_refuse_absence():
    with pytest.raises(BaremeIndisponible):
        calculer_bareme_depuis_registre(
            "100", [], "2026-01-01", code="TEST_PROGRESSIF",
        )


def test_selection_ignore_projet_non_active():
    assert calculer_bareme_depuis_registre(
        "201", [regle(statut_juridique="projet"), regle()],
        "2026-01-01", code="TEST_PROGRESSIF",
    )["montant"] == "10.20"


def test_selection_refuse_type_incompatible():
    with pytest.raises(BaremeIndisponible):
        calculer_bareme_depuis_registre(
            "201", [regle(type_regle="echeance")],
            "2026-01-01", code="TEST_PROGRESSIF",
        )
