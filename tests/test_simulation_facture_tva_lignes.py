"""Contrats de simulation TVA par ligne. Taux et sources FICTIFS uniquement."""
from datetime import date
from decimal import Decimal

import pytest

from core.classification_fiscale import ClassificationIndisponible
from core.fiscalite_facturation import FiscaliteNonDisponible
from core.simulation_facture_tva_lignes import simuler_tva_facture_lignes


def classe(sku, categorie):
    return {
        "sku_id": sku, "date_effet": "2026-01-01", "date_fin": None,
        "statut": "VALIDEE", "categorie_tva": categorie,
        "code_parametre": f"TVA_TAUX_{categorie}",
        "source_juridique": "SOURCE-TEST-FICTIVE",
        "justification": "EXEMPLE", "valide_par": "TEST",
        "date_verification": "2026-01-02", "date_validation": "2026-01-03",
    }


def param(code, taux):
    return {
        "code": code, "valeur": taux, "unite": "fraction",
        "statut_juridique": "en_vigueur", "niveau_confiance": "CONFIRMEE",
        "source": "SOURCE-TEST-FICTIVE", "date_effet": "2026-01-01",
        "date_fin": None, "date_verification": "2026-01-02",
    }


def catalogue():
    return (
        [classe("SKU-A", "NORMAL"), classe("SKU-B", "NORMAL")],
        [param("TVA_TAUX_NORMAL", "0.19")],
    )


def panier():
    return [
        {"sku_id": "SKU-A", "quantite": "2", "prix_unitaire": "12.345", "remise": "0.01"},
        {"sku_id": "SKU-B", "quantite": "1", "prix_unitaire": "10.055", "remise": "0"},
    ]


def calcul(lignes=None, **kwargs):
    classes, parametres = catalogue()
    return simuler_tva_facture_lignes(
        panier() if lignes is None else lignes,
        date(2026, 2, 1), classes, parametres, **kwargs,
    )


def test_simulation_tva_mixte_par_ligne():
    result = calcul()
    assert [row["montant_ht"] for row in result["lignes"]] == [
        Decimal("24.68"), Decimal("10.06"),
    ]
    assert [row["montant_tva"] for row in result["lignes"]] == [
        Decimal("4.69"), Decimal("1.91"),
    ]
    assert result["montant_ht"] == Decimal("34.74")
    assert result["montant_tva"] == Decimal("6.60")
    assert result["montant_ttc"] == Decimal("41.34")
    assert result["montant_timbre"] == 0
    assert result["simulation_sans_ecriture"] is True
    assert result["autorise_activation_facturation"] is False


def test_une_seule_classification_absente_bloque_facture():
    classes, parametres = catalogue()
    with pytest.raises(ClassificationIndisponible):
        simuler_tva_facture_lignes(panier(), date(2026, 2, 1), classes[:1], parametres)


@pytest.mark.parametrize("kwargs", [
    {"remise_globale": "1.00"}, {"paiement_especes": True},
    {"paiement_especes": "false"}, {"remise_globale": 0.0},
])
def test_options_non_homologuees_refusees(kwargs):
    with pytest.raises(FiscaliteNonDisponible):
        calcul(**kwargs)


@pytest.mark.parametrize("lignes", [
    [], [{"sku_id": "SKU-A", "quantite": "0", "prix_unitaire": "1"}],
    [{"sku_id": "SKU-A", "quantite": "1.5", "prix_unitaire": "1"}],
    [{"sku_id": "SKU-A", "quantite": "1", "prix_unitaire": "5", "remise": "6"}],
    [{"sku_id": "SKU-A", "quantite": 1, "prix_unitaire": 1.0}],
    [{"sku_id": "SKU-A", "quantite": "1", "prix_unitaire": "-1"}],
])
def test_panier_financier_invalide_refuse(lignes):
    with pytest.raises(FiscaliteNonDisponible):
        calcul(lignes)


def test_taux_non_confirme_refuse():
    classes, parametres = catalogue()
    parametres[0]["niveau_confiance"] = "A_CONFIRMER"
    with pytest.raises(FiscaliteNonDisponible):
        simuler_tva_facture_lignes(panier(), date(2026, 2, 1), classes, parametres)


def test_precision_arrondi_centime():
    result = calcul([{"sku_id": "SKU-A", "quantite": "1",
                      "prix_unitaire": "0.005", "remise": "0"}])
    assert result["montant_ht"] == Decimal("0.01")


def test_classification_provisoire_chevauchante_bloque_toute_facture():
    classes, parametres = catalogue()
    classes.append({
        "sku_id": "SKU-B", "date_effet": "2026-01-15",
        "date_fin": None, "statut": "A_VALIDER",
        "categorie_tva": None, "code_parametre": None,
    })
    with pytest.raises(ClassificationIndisponible, match="attente de validation"):
        simuler_tva_facture_lignes(
            panier(), date(2026, 2, 1), classes, parametres
        )


def test_simulation_capture_preuve_par_ligne_sans_ecriture():
    resultat = calcul()
    assert len(resultat["lignes"]) == 2
    a, b = resultat["lignes"]
    assert a["justificatif_classification"]["sku_id"] == "SKU-A"
    assert b["justificatif_classification"]["sku_id"] == "SKU-B"
    assert a["justificatif_classification"]["code_parametre"] == "TVA_TAUX_NORMAL"
    assert b["justificatif_classification"]["code_parametre"] == "TVA_TAUX_NORMAL"
    assert a["justificatif_classification"]["date_validation"] == "2026-01-03"
    assert a["justificatif_taux"]["date_verification"] == "2026-01-02"
    assert resultat["simulation_sans_ecriture"] is True
    assert resultat["autorise_activation_facturation"] is False


def attestation_client():
    return {
        "client_id": "CLI-TEST", "statut": "VALIDEE",
        "date_effet": "2026-01-01", "date_fin": "2026-12-31",
        "date_verification": "2026-01-02", "date_validation": "2026-01-03",
        "reference_attestation": "CERTIFICAT-FICTIF",
        "autorite_emettrice": "AUTORITE-FICTIVE",
        "valide_par": "SIGNATAIRE-FICTIF", "justification": "SKU-B UNIQUEMENT",
        "sku_ids_couverts": ["SKU-B"],
    }


def test_facture_avec_client_exonere_pour_un_sku_seulement():
    r = calcul(client_id="CLI-TEST", attestation_exoneration=attestation_client())
    assert [x["mode_tva"] for x in r["lignes"]] == [
        "NORMAL", "EXONERATION_CLIENT"
    ]
    assert [x["taux_tva"] for x in r["lignes"]] == [
        Decimal("0.19"), Decimal("0")
    ]
    assert r["lignes"][1]["justificatif_exoneration_client"]["client_id"] == "CLI-TEST"
    assert r["lignes"][0]["justificatif_exoneration_client"] is None
    assert r["montant_tva"] == Decimal("4.69")
    assert r["montant_ttc"] == Decimal("39.43")
    assert r["autorise_activation_facturation"] is False


def test_exoneration_client_non_validee_bloque_simulation():
    attestation = attestation_client()
    attestation["statut"] = "A_VALIDER"
    with pytest.raises(FiscaliteNonDisponible, match="non validée"):
        calcul(client_id="CLI-TEST", attestation_exoneration=attestation)


def test_attestation_client_autre_bloque_simulation():
    with pytest.raises(FiscaliteNonDisponible, match="autre client"):
        calcul(client_id="CLI-AUTRE", attestation_exoneration=attestation_client())


def test_exoneration_ne_peut_pas_etre_induite_par_la_categorie_sku():
    classifications, params = catalogue()
    classifications[1]["categorie_tva"] = "EXONERE"
    classifications[1]["code_parametre"] = None
    with pytest.raises(ClassificationIndisponible):
        simuler_tva_facture_lignes(
            panier(), date(2026, 2, 1), classifications, params,
            client_id="CLI-TEST", attestation_exoneration=attestation_client()
        )
