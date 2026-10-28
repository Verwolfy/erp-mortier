"""Tests indépendants de Supabase, Google Sheets et de taux algériens réels."""
from __future__ import annotations

from decimal import Decimal

import pytest

from core.reglementation import RegleIndisponible, calculer_pourcentage, chercher_parametre


def row(**change):
    sample = dict(
        code="EXEMPLE_TAUX", valeur="0.125", date_effet="2026-01-01",
        date_fin=None, statut_juridique="en_vigueur",
        niveau_confiance="CONFIRMEE", source="SOURCE_FICTIVE_TEST",
        date_verification="2026-01-03",
    )
    sample.update(change)
    return sample


def test_valeur_a_date_effet_et_tracabilite():
    p = chercher_parametre([row()], "EXEMPLE_TAUX", "2026-01-01")
    assert p.valeur == Decimal("0.125")
    result = calculer_pourcentage("100.00", [row()], "EXEMPLE_TAUX", "2026-01-03")
    assert result == dict(code="EXEMPLE_TAUX", assiette="100.00", taux="0.125",
                          montant="12.50", date_operation="2026-01-03",
                          date_effet="2026-01-01", source="SOURCE_FICTIVE_TEST",
                          date_verification="2026-01-03")


def test_versions_non_chevauchantes():
    values = [row(date_fin="2026-06-30"),
              row(valeur="0.20", date_effet="2026-07-01")]
    assert chercher_parametre(values, "EXEMPLE_TAUX", "2026-06-30").valeur == Decimal("0.125")
    assert chercher_parametre(values, "EXEMPLE_TAUX", "2026-07-01").valeur == Decimal("0.20")


@pytest.mark.parametrize("change", [
    {"statut_juridique": "projet"},
    {"statut_juridique": "a_confirmer"},
    {"statut_juridique": "abrogee"},
    {"niveau_confiance": "NON_VERIFIEE"},
])
def test_valeurs_non_confirmees_bloquees(change):
    with pytest.raises(RegleIndisponible):
        chercher_parametre([row(**change)], "EXEMPLE_TAUX", "2026-03-01")


def test_ambiguites_bloquees():
    with pytest.raises(RegleIndisponible, match="2 règle"):
        chercher_parametre([row(), row(valeur="0.15")], "EXEMPLE_TAUX", "2026-03-01")


@pytest.mark.parametrize("change", [
    {"source": ""},
    {"date_effet": "2026-02-30"},
    {"date_fin": "2025-12-31"},
    {"date_verification": None},
])
def test_parametres_invalides_bloques(change):
    with pytest.raises(RegleIndisponible):
        chercher_parametre([row(**change)], "EXEMPLE_TAUX", "2026-03-01")


@pytest.mark.parametrize("invalid", [float("nan"), 0.5, "NaN", "Infinity", -1, True])
def test_assiette_non_exacte_ou_invalide_bloquee(invalid):
    with pytest.raises(RegleIndisponible):
        calculer_pourcentage(invalid, [row()], "EXEMPLE_TAUX", "2026-03-01")


def test_pas_de_valeur_par_defaut_ni_taux_sup_a_un():
    with pytest.raises(RegleIndisponible):
        chercher_parametre([], "EXEMPLE_TAUX", "2026-03-01")
    with pytest.raises(RegleIndisponible):
        calculer_pourcentage("100", [row(valeur="1.2")], "EXEMPLE_TAUX", "2026-03-01")


def test_arrondi_decimal_half_up():
    result = calculer_pourcentage("1.00", [row(valeur="0.125")], "EXEMPLE_TAUX", "2026-03-01")
    assert result["montant"] == "0.13"
