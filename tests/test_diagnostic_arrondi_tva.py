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


def test_taux_multiples_ne_sont_pas_comparables_globalement():
    s = simuler_tva_facture_lignes(
        [
            {"sku_id": "SKU-X", "quantite": "1", "prix_unitaire": "10"},
            {"sku_id": "SKU-Y", "quantite": "1", "prix_unitaire": "10"},
        ],
        date(2026, 2, 1),
        [classification(), classification("SKU-Y", "REDUIT")],
        [parametre(), parametre("REDUIT", "0.09")],
    )
    with pytest.raises(FiscaliteNonDisponible, match="Taux multiples"):
        comparer_arrondis_tva(s)


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
