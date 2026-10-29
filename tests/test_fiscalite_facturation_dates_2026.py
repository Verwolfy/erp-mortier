"""Non-régression du moteur fiscal pur, sans accès à Supabase.

Ces taux sont des fixtures fictives uniquement, jamais des règles algériennes.
"""
from decimal import Decimal

import pytest

from core.fiscalite_facturation import FiscaliteNonDisponible, calculer_taxes_facture


def _param(value, start, end=None, *, status="en_vigueur", confidence="CONFIRMEE", source="FIXTURE-TEST"):
    return {
        "code": "TVA_VENTE_TAUX",
        "valeur": str(value),
        "unite": "fraction",
        "statut_juridique": status,
        "niveau_confiance": confidence,
        "source": source,
        "date_effet": start,
        "date_fin": end,
        "date_verification": "2026-01-01",
    }


def test_dates_effet_retroactivite_et_arrondi():
    params = [
        _param("0.13", "2025-01-01", "2025-12-31"),
        _param("0.17", "2026-01-01"),
    ]
    old = calculer_taxes_facture("10.03", False, "2025-12-31", params)
    new = calculer_taxes_facture("10.03", False, "2026-01-01", params)
    assert old["montant_tva"] == Decimal("1.30")
    assert new["montant_tva"] == Decimal("1.71")
    assert old["montant_timbre"] == new["montant_timbre"] == Decimal("0.00")
    assert old["montant_ttc"] == Decimal("11.33")
    assert new["montant_ttc"] == Decimal("11.74")
    assert old["justificatifs"][0]["date_effet"] == "2025-01-01"
    assert new["justificatifs"][0]["date_effet"] == "2026-01-01"


@pytest.mark.parametrize("params", [
    [],
    [_param("0.17", "2027-01-01")],
    [_param("0.17", "2026-01-01", status="a_confirmer")],
    [_param("0.17", "2026-01-01", status="projet")],
    [_param("0.17", "2026-01-01", confidence="NON_VERIFIEE")],
])
def test_absence_ou_non_validation_refuse_le_calcul(params):
    with pytest.raises(FiscaliteNonDisponible):
        calculer_taxes_facture("100", False, "2026-02-01", params)


def test_periodes_chevauchantes_refusees():
    params = [
        _param("0.13", "2026-01-01", "2026-06-30"),
        _param("0.17", "2026-06-01"),
    ]
    with pytest.raises(FiscaliteNonDisponible, match="2 valeur"):
        calculer_taxes_facture("100", False, "2026-06-15", params)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "1000000000000000", 1.5])
def test_montants_invalides_refuses(value):
    with pytest.raises(FiscaliteNonDisponible):
        calculer_taxes_facture(value, False, "2026-02-01", [_param("0.17", "2026-01-01")])


def test_especes_refusees_meme_si_parametres_presents():
    with pytest.raises(FiscaliteNonDisponible, match="timbre"):
        calculer_taxes_facture("100", True, "2026-02-01", [_param("0.17", "2026-01-01")])


def test_source_absente_refusee():
    with pytest.raises(FiscaliteNonDisponible, match="source"):
        calculer_taxes_facture("100", False, "2026-02-01", [_param("0.17", "2026-01-01", source="")])


def test_taux_hors_plage_refuse():
    with pytest.raises(FiscaliteNonDisponible, match="Taux TVA invalide"):
        calculer_taxes_facture("100", False, "2026-02-01", [_param("1.5", "2026-01-01")])


def test_parametre_unite_incompatible_bloque_calcul():
    ligne = _param("0.17", "2026-01-01")
    ligne["unite"] = "DZD"
    with pytest.raises(FiscaliteNonDisponible, match="unité incompatible"):
        calculer_taxes_facture("100", False, "2026-02-01", [ligne])


def test_date_facture_invalide_refusee():
    with pytest.raises(FiscaliteNonDisponible, match="Date fiscale"):
        calculer_taxes_facture("100", False, "2026-02-30", [_param("0.17", "2026-01-01")])


def test_faux_montant_booleen_refuse():
    with pytest.raises(FiscaliteNonDisponible, match="décimal exact"):
        calculer_taxes_facture(True, False, "2026-02-01", [_param("0.17", "2026-01-01")])


def test_taux_change_sans_modifier_code():
    ancien = [_param("0.11", "2026-01-01")]
    nouveau = [_param("0.18", "2026-01-01")]
    a = calculer_taxes_facture("100", False, "2026-02-01", ancien)
    b = calculer_taxes_facture("100", False, "2026-02-01", nouveau)
    assert a["montant_tva"] == Decimal("11.00")
    assert b["montant_tva"] == Decimal("18.00")
    assert a["montant_ttc"] != b["montant_ttc"]
