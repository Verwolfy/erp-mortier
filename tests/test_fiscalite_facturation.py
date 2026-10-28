"""Paramètres fictifs uniquement : ce fichier ne valide aucune valeur juridique."""
from decimal import Decimal

import pytest

from core.fiscalite_facturation import calculer_taxes_facture, FiscaliteNonDisponible


def param(code, valeur, unite="fraction", **kwargs):
    data = {
        "code": code, "valeur": valeur, "unite": unite,
        "statut_juridique": "en_vigueur", "niveau_confiance": "CONFIRMEE",
        "source": "FICTION-TEST", "date_effet": "2026-01-01",
        "date_fin": None, "date_verification": "2026-01-02",
    }
    data.update(kwargs)
    return data


def params():
    return [
        param("TVA_VENTE_TAUX", "0.19"),
        param("TIMBRE_ESPECES_TAUX", "0.01"),
        param("TIMBRE_ESPECES_PLAFOND", "2500", "DZD"),
    ]


def test_simulation_facture_sans_especes():
    r = calculer_taxes_facture("185.00", False, "2026-10-28", params())
    assert r["montant_tva"] == Decimal("35.15")
    assert r["montant_timbre"] == Decimal(0)
    assert r["montant_ttc"] == Decimal("220.15")
    assert len(r["justificatifs"]) == 1


def test_especes_plafond_et_trace():
    r = calculer_taxes_facture("1000000", True, "2026-10-28", params())
    assert r["montant_timbre"] == Decimal("2500.00")
    assert len(r["justificatifs"]) == 3


@pytest.mark.parametrize("modification", [
    {"statut_juridique": "projet"}, {"niveau_confiance": "NON_VERIFIEE"},
    {"source": ""}, {"unite": "pct"}, {"date_effet": "2027-01-01"},
    {"date_verification": None}, {"date_fin": "2025-12-01"},
    {"valeur": "NaN"}, {"valeur": "1.5"},
])
def test_tva_invalide_refusee(modification):
    p = params()
    p[0].update(modification)
    with pytest.raises(FiscaliteNonDisponible):
        calculer_taxes_facture("1", False, "2026-10-28", p)


def test_taux_chevauchants_refuses():
    with pytest.raises(FiscaliteNonDisponible):
        calculer_taxes_facture("1", False, "2026-10-28", params() + [params()[0]])


@pytest.mark.parametrize("value", [True, 1.5, "NaN", "Infinity", "-1", None])
def test_assiette_invalide(value):
    with pytest.raises(FiscaliteNonDisponible):
        calculer_taxes_facture(value, False, "2026-10-28", params())


def test_pas_de_timbre_sans_especes():
    assert calculer_taxes_facture("10", False, "2026-10-28", params()[:1])["montant_timbre"] == 0
    with pytest.raises(FiscaliteNonDisponible):
        calculer_taxes_facture("10", True, "2026-10-28", params()[:1])


def test_taux_date_effet():
    pp = params()
    pp[0]["date_fin"] = "2026-06-30"
    pp += [param("TVA_VENTE_TAUX", "0.21", date_effet="2026-07-01")]
    assert calculer_taxes_facture("100", False, "2026-06-30", pp)["montant_tva"] == Decimal("19.00")
    assert calculer_taxes_facture("100", False, "2026-07-01", pp)["montant_tva"] == Decimal("21.00")


def test_decimal_round_half_up():
    assert calculer_taxes_facture("0.05", False, "2026-10-28", [
        param("TVA_VENTE_TAUX", "0.1")
    ])["montant_tva"] == Decimal("0.01")
