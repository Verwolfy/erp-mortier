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


def test_especes_timbre_ancienne_formule_refusee():
    with pytest.raises(FiscaliteNonDisponible, match="timbre sur facture interdit"):
        calculer_taxes_facture("1000000", True, "2026-10-28", params())


def test_absence_de_timbre_fiscal_si_paiement_non_especes():
    r = calculer_taxes_facture("100", False, "2026-10-28", params())
    assert r["montant_timbre"] == Decimal("0.00")
    assert len(r["justificatifs"]) == 1


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


# Nouveau calcul isolé : scénarios métier fictifs, sans classification réelle.
from core.fiscalite_facturation import calculer_tva_lignes_classees


def ligne(sku="SKU-FICTIF-1", ht="100.00", code="TVA_TAUX_NORMAL", **options):
    result = {
        "sku_id": sku, "montant_ht": ht, "code_tva": code,
        "classification_verifiee": True,
        "source_classification": "FICHIER-FICTIF-TEST",
    }
    result.update(options)
    return result


def test_tva_lignes_classees_melange_deux_regimes_fictifs():
    registre = [
        param("TVA_TAUX_NORMAL", "0.20"),
        param("TVA_TAUX_REDUIT", "0.07"),
    ]
    result = calculer_tva_lignes_classees([
        ligne(ht="100.00"),
        ligne(sku="SKU-FICTIF-2", ht="50.00", code="TVA_TAUX_REDUIT"),
    ], "2026-11-09", registre)
    assert result["montant_ht"] == Decimal("150.00")
    assert result["montant_tva"] == Decimal("23.50")
    assert result["montant_ttc"] == Decimal("173.50")
    assert result["montant_timbre"] == Decimal("0.00")
    assert len(result["lignes"]) == 2
    assert all(x["justificatif_taux"]["source"] == "FICTION-TEST" for x in result["lignes"])
    assert result["statut"] == "CALCUL_ISOLE_NON_COMPTABILISE"


def test_tva_lignes_classees_versionnement_fictif():
    registre = [
        param("TVA_TAUX_NORMAL", "0.12", date_fin="2026-06-30"),
        param("TVA_TAUX_NORMAL", "0.13", date_effet="2026-07-01"),
    ]
    assert calculer_tva_lignes_classees(
        [ligne()], "2026-06-30", registre
    )["montant_tva"] == Decimal("12.00")
    assert calculer_tva_lignes_classees(
        [ligne()], "2026-07-01", registre
    )["montant_tva"] == Decimal("13.00")


@pytest.mark.parametrize("modification", [
    {"classification_verifiee": False},
    {"classification_verifiee": "true"},
    {"source_classification": ""},
    {"code_tva": "TVA_VENTE_TAUX"},
    {"code_tva": "TVA_EXONERE"},
    {"montant_ht": "-1"},
    {"montant_ht": "NaN"},
    {"montant_ht": "1.001"},
    {"montant_ht": 1.5},
    {"sku_id": ""},
])
def test_tva_lignes_classees_refuse_donnees_non_qualifiees(modification):
    with pytest.raises(FiscaliteNonDisponible):
        calculer_tva_lignes_classees(
            [ligne(**modification)], "2026-11-09",
            [param("TVA_TAUX_NORMAL", "0.20")]
        )


@pytest.mark.parametrize("registre", [
    [],
    [param("TVA_TAUX_NORMAL", "0.20", statut_juridique="a_confirmer")],
    [param("TVA_TAUX_NORMAL", "0.20"),
     param("TVA_TAUX_NORMAL", "0.21")],
    [param("TVA_TAUX_NORMAL", "1.20")],
])
def test_tva_lignes_classees_refuse_registre_ambigu(registre):
    with pytest.raises(FiscaliteNonDisponible):
        calculer_tva_lignes_classees([ligne()], "2026-11-09", registre)


def test_tva_lignes_classees_refuse_timbre_especes():
    with pytest.raises(FiscaliteNonDisponible, match="Timbre espèces"):
        calculer_tva_lignes_classees(
            [ligne()], "2026-11-09",
            [param("TVA_TAUX_NORMAL", "0.20")],
            paiement_especes=True,
        )


def test_tva_lignes_classees_refuse_sku_duplique():
    with pytest.raises(FiscaliteNonDisponible, match="dupliqué"):
        calculer_tva_lignes_classees(
            [ligne(), ligne()], "2026-11-09",
            [param("TVA_TAUX_NORMAL", "0.20")],
        )
