"""Contrats d'écart TVA ; valeurs fictives, aucune règle algérienne inférée."""
from copy import deepcopy
from datetime import date
from decimal import Decimal

import pytest

from core.diagnostic_arrondi_tva import comparer_arrondis_tva
from core.fiscalite_facturation import FiscaliteNonDisponible
from core.simulation_facture_tva_lignes import simuler_tva_facture_lignes


def classification(sku="SKU-X", cat="NORMAL"):
    return {
        "sku_id": sku, "date_effet": "2026-01-01", "date_fin": None,
        "statut": "VALIDEE", "categorie_tva": cat,
        "code_parametre": f"TVA_TAUX_{cat}",
        "source_juridique": "SOURCE-TEST-FICTIVE", "justification": "TEST",
        "valide_par": "TEST", "date_verification": "2026-01-02",
        "date_validation": "2026-01-03",
    }


def parametre(cat="NORMAL", taux="0.17"):
    return {
        "code": f"TVA_TAUX_{cat}", "valeur": taux, "unite": "fraction",
        "statut_juridique": "en_vigueur", "niveau_confiance": "CONFIRMEE",
        "source": "SOURCE-TEST-FICTIVE", "date_effet": "2026-01-01",
        "date_fin": None, "date_verification": "2026-01-02",
    }


def simulation(prix="0.03"):
    return simuler_tva_facture_lignes(
        [
            {"sku_id": "SKU-X", "quantite": "1", "prix_unitaire": prix},
            {"sku_id": "SKU-X", "quantite": "1", "prix_unitaire": prix},
        ],
        date(2026, 2, 1), [classification()], [parametre()],
    )


def test_ecart_arrondi_par_ligne_versus_global_documente():
    audit = comparer_arrondis_tva(simulation())
    assert audit["montant_ht"] == Decimal("0.06")
    assert audit["tva_arrondie_par_ligne"] == Decimal("0.02")
    assert audit["tva_arrondie_globalement"] == Decimal("0.01")
    assert audit["ecart"] == Decimal("0.01")
    assert audit["statut"] == "ECART"
    assert audit["conventions_non_homologuees"] is True
    assert audit["autorise_activation_facturation"] is False


def test_concordance_possible_ne_vaut_pas_approbation():
    audit = comparer_arrondis_tva(simulation(prix="10.00"))
    assert audit["tva_arrondie_par_ligne"] == Decimal("3.40")
    assert audit["tva_arrondie_globalement"] == Decimal("3.40")
    assert audit["statut"] == "CONCORDANT"
    assert audit["autorise_activation_facturation"] is False


def test_taux_multiples_comparables_seulement_par_groupe_fiscal():
    s = simuler_tva_facture_lignes(
        [
            {"sku_id": "SKU-X", "quantite": "1", "prix_unitaire": "0.03"},
            {"sku_id": "SKU-X", "quantite": "1", "prix_unitaire": "0.03"},
            {"sku_id": "SKU-Y", "quantite": "1", "prix_unitaire": "0.03"},
            {"sku_id": "SKU-Y", "quantite": "1", "prix_unitaire": "0.03"},
        ],
        date(2026, 2, 1),
        [classification(), classification("SKU-Y", "REDUIT")],
        [parametre(), parametre("REDUIT", "0.09")],
    )
    result = comparer_arrondis_tva(s)
    assert result["nombre_groupes"] == 2
    assert result["taux_comparatif"] is None
    assert result["montant_ht"] == Decimal("0.12")
    assert result["tva_arrondie_par_ligne"] == Decimal("0.02")
    assert result["tva_arrondie_globalement"] == Decimal("0.02")
    assert result["ecart"] == Decimal("0.00")
    assert [(g["code_parametre"], g["ecart"]) for g in result["groupes_tva"]] == [
        ("TVA_TAUX_NORMAL", Decimal("0.01")),
        ("TVA_TAUX_REDUIT", Decimal("-0.01")),
    ]
    assert result["conventions_non_homologuees"] is True
    assert result["autorise_activation_facturation"] is False


@pytest.mark.parametrize("update", [
    {"autorise_activation_facturation": True},
    {"simulation_sans_ecriture": False},
    {"lignes": []},
    {"montant_tva": Decimal("0.03")},
    {"montant_ttc": Decimal("0.09")},
])
def test_simulation_falsifiee_refusee(update):
    donnees = deepcopy(simulation())
    donnees.update(update)
    with pytest.raises(FiscaliteNonDisponible):
        comparer_arrondis_tva(donnees)


def test_ligne_falsifiee_refusee():
    donnees = deepcopy(simulation())
    donnees["lignes"][0]["montant_tva"] = Decimal("0.02")
    with pytest.raises(FiscaliteNonDisponible, match="TVA ligne incohérente"):
        comparer_arrondis_tva(donnees)


def test_diagnostic_ne_modifie_pas_simulation():
    donnees = simulation()
    avant = deepcopy(donnees)
    comparer_arrondis_tva(donnees)
    assert donnees == avant


def test_comparaison_mono_groupe_conserve_contrat_historique():
    r = comparer_arrondis_tva(simulation())
    assert r["nombre_groupes"] == 1
    assert r["taux_comparatif"] == Decimal("0.17")
    assert r["groupes_tva"][0]["ecart"] == Decimal("0.01")


@pytest.mark.parametrize("field,value", [
    ("categorie_tva", "EXONERE"),
    ("categorie_tva", "INCONNUE"),
    ("categorie_tva", None),
    ("justificatif_taux", None),
    ("justificatif_taux", {"code": "TVA_TAUX_REDUIT"}),
    ("montant_ttc", Decimal("0.05")),
    ("sku_id", ""),
])
def test_ligne_qualifiante_incoherente_refusee(field, value):
    s = deepcopy(simulation())
    s["lignes"][0][field] = value
    with pytest.raises(FiscaliteNonDisponible):
        comparer_arrondis_tva(s)


def test_timbre_sur_facture_refuse():
    s = deepcopy(simulation())
    s["montant_timbre"] = Decimal("0.01")
    with pytest.raises(FiscaliteNonDisponible, match="Timbre"):
        comparer_arrondis_tva(s)


def test_comparaison_ne_modifie_pas_entree_multitaux():
    s = simuler_tva_facture_lignes(
        [{"sku_id": "SKU-X", "quantite": "1", "prix_unitaire": "5"},
         {"sku_id": "SKU-Y", "quantite": "1", "prix_unitaire": "5"}],
        date(2026, 2, 1),
        [classification(), classification("SKU-Y", "REDUIT")],
        [parametre(), parametre("REDUIT", "0.09")],
    )
    before = deepcopy(s)
    comparer_arrondis_tva(s)
    assert s == before
