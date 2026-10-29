"""Diagnostic d'arrondi ventes ERP : 19% nominal ou exonération client, tests fictifs."""
from copy import deepcopy
from datetime import date
from decimal import Decimal

import pytest

from core.diagnostic_arrondi_tva import comparer_arrondis_tva
from core.fiscalite_facturation import FiscaliteNonDisponible
from core.simulation_facture_tva_lignes import simuler_tva_facture_lignes


def classification(sku="SKU-X"):
    return {
        "sku_id": sku, "date_effet": "2026-01-01", "date_fin": None,
        "statut": "VALIDEE", "categorie_tva": "NORMAL",
        "code_parametre": "TVA_TAUX_NORMAL",
        "source_juridique": "SOURCE-TEST-FICTIVE", "justification": "TEST",
        "valide_par": "TEST", "date_verification": "2026-01-02",
        "date_validation": "2026-01-03",
    }


def parametre():
    return {
        "code": "TVA_TAUX_NORMAL", "valeur": "0.19", "unite": "fraction",
        "statut_juridique": "en_vigueur", "niveau_confiance": "CONFIRMEE",
        "source": "SOURCE-TEST-FICTIVE", "date_effet": "2026-01-01",
        "date_fin": None, "date_verification": "2026-01-02",
    }


def attestation():
    return {
        "client_id": "CLI-TEST", "statut": "VALIDEE",
        "date_effet": "2026-01-01", "date_fin": "2026-12-31",
        "date_verification": "2026-01-02", "date_validation": "2026-01-03",
        "reference_attestation": "EXO-FICTIVE",
        "autorite_emettrice": "AUTORITE-FICTIVE",
        "valide_par": "VALIDATEUR-FICTIF", "justification": "SKU-Y uniquement",
        "sku_ids_couverts": ["SKU-Y"],
    }


def simulation(prix="0.03"):
    return simuler_tva_facture_lignes(
        [{"sku_id": "SKU-X", "quantite": "1", "prix_unitaire": prix},
         {"sku_id": "SKU-X", "quantite": "1", "prix_unitaire": prix}],
        date(2026, 2, 1), [classification()], [parametre()],
    )


def simulation_mixte(prix="0.03"):
    return simuler_tva_facture_lignes(
        [{"sku_id": "SKU-X", "quantite": "1", "prix_unitaire": prix},
         {"sku_id": "SKU-X", "quantite": "1", "prix_unitaire": prix},
         {"sku_id": "SKU-Y", "quantite": "1", "prix_unitaire": prix},
         {"sku_id": "SKU-Y", "quantite": "1", "prix_unitaire": prix}],
        date(2026, 2, 1), [classification(), classification("SKU-Y")],
        [parametre()], client_id="CLI-TEST",
        attestation_exoneration=attestation(),
    )


def test_ecart_arrondi_par_ligne_versus_global_documente():
    audit = comparer_arrondis_tva(simulation())
    assert audit["montant_ht"] == Decimal("0.06")
    assert audit["tva_arrondie_par_ligne"] == Decimal("0.02")
    assert audit["tva_arrondie_globalement"] == Decimal("0.01")
    assert audit["ecart"] == Decimal("0.01")
    assert audit["statut"] == "ECART"
    assert audit["nombre_groupes_en_ecart"] == 1
    assert audit["conventions_non_homologuees"] is True
    assert audit["autorise_activation_facturation"] is False


def test_concordance_possible_ne_vaut_pas_approbation():
    audit = comparer_arrondis_tva(simulation(prix="10.00"))
    assert audit["tva_arrondie_par_ligne"] == Decimal("3.80")
    assert audit["tva_arrondie_globalement"] == Decimal("3.80")
    assert audit["statut"] == "CONCORDANT"
    assert audit["autorise_activation_facturation"] is False


def test_exoneration_client_cree_deux_groupes_19_et_zero():
    result = comparer_arrondis_tva(simulation_mixte())
    assert result["nombre_groupes"] == 2
    assert result["taux_comparatif"] is None
    assert result["montant_ht"] == Decimal("0.12")
    assert result["tva_arrondie_par_ligne"] == Decimal("0.02")
    assert result["tva_arrondie_globalement"] == Decimal("0.01")
    assert result["ecart"] == Decimal("0.01")
    assert result["nombre_groupes_en_ecart"] == 1
    assert result["statut"] == "ECART"
    details = {g["mode_tva"]: g for g in result["groupes_tva"]}
    assert details["NORMAL"]["taux_tva"] == Decimal("0.19")
    assert details["NORMAL"]["ecart"] == Decimal("0.01")
    assert details["EXONERATION_CLIENT"]["taux_tva"] == Decimal("0")
    assert details["EXONERATION_CLIENT"]["ecart"] == Decimal("0")
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


@pytest.mark.parametrize("field,value", [
    ("categorie_tva", "REDUIT"),
    ("categorie_tva", "EXONERE"),
    ("categorie_tva", None),
    ("categorie_tva", ["NORMAL"]),
    ("justificatif_taux", None),
    ("justificatif_taux", {"code": "TVA_TAUX_REDUIT"}),
    ("montant_ttc", Decimal("0.05")),
    ("mode_tva", "EXONERATION_CLIENT"),
    ("mode_tva", "INCONNU"),
    ("sku_id", ""),
])
def test_ligne_fiscale_falsifiee_refusee(field, value):
    s = deepcopy(simulation())
    s["lignes"][0][field] = value
    with pytest.raises(FiscaliteNonDisponible):
        comparer_arrondis_tva(s)


def test_tva_ligne_incoherente_refusee():
    s = deepcopy(simulation())
    s["lignes"][0]["montant_tva"] = Decimal("0.02")
    with pytest.raises(FiscaliteNonDisponible, match="TVA ligne incohérente"):
        comparer_arrondis_tva(s)


def test_attestation_falsifiee_refusee():
    s = deepcopy(simulation_mixte())
    s["lignes"][2]["justificatif_exoneration_client"]["date_fin"] = "2025-12-31"
    with pytest.raises(FiscaliteNonDisponible):
        comparer_arrondis_tva(s)


def test_timbre_sur_facture_refuse():
    s = deepcopy(simulation())
    s["montant_timbre"] = Decimal("0.01")
    with pytest.raises(FiscaliteNonDisponible, match="Timbre"):
        comparer_arrondis_tva(s)


def test_diagnostic_ne_modifie_pas_simulation():
    s = simulation_mixte()
    before = deepcopy(s)
    comparer_arrondis_tva(s)
    assert s == before


def test_comparaison_mono_groupe_conserve_contrat_historique():
    r = comparer_arrondis_tva(simulation())
    assert r["nombre_groupes"] == 1
    assert r["nombre_groupes_en_ecart"] == 1
    assert r["taux_comparatif"] == Decimal("0.19")
    assert r["groupes_tva"][0]["ecart"] == Decimal("0.01")


def test_tous_les_groupes_concordants_sont_vraiment_concordants():
    result = comparer_arrondis_tva(simulation_mixte(prix="100.00"))
    assert result["nombre_groupes"] == 2
    assert result["nombre_groupes_en_ecart"] == 0
    assert result["statut"] == "CONCORDANT"
    assert result["autorise_activation_facturation"] is False
