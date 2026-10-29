"""Contrats d'analyse de composantes de paie ; données fictives uniquement."""
from decimal import Decimal
from copy import deepcopy
import pytest

from core.paie_assiettes import AssiettesNonDisponibles, consolider_assiettes_paie


def preuve(code="PR-TEST"):
    return {
        "code": code, "source": "SOURCE_SYNTHETIQUE_TEST",
        "statut": "CONFIRMEE", "date_effet": "2026-01-01",
        "date_fin": None, "date_verification": "2026-10-01",
    }


def ligne(ident="L1", montant="100.00", **changes):
    item = {
        "element_id": ident, "libelle": "Gain fictif",
        "type_mouvement": "GAIN", "montant": montant,
        "traitement_cnas": "INCLUS", "traitement_irg": "INCLUS",
        "preuve_cnas": preuve("CNAS-TEST"),
        "preuve_irg": preuve("IRG-TEST"),
    }
    item.update(changes)
    return item


def audit(items=None):
    return consolider_assiettes_paie(
        [ligne()] if items is None else items,
        "2026-10-29",
    )


def test_composantes_positives_classification_explicite():
    x = audit([
        ligne("SAL-1","1000.00"),
        ligne("INDEMNITE-1","250.30",traitement_cnas="EXCLU",traitement_irg="INCLUS"),
        ligne("REMBOURSEMENT_FICTIF_GAIN","50",traitement_cnas="EXCLU",traitement_irg="EXCLU"),
    ])
    assert x["brut_reconstitue"] == "1300.30"
    assert x["composantes_cnas_avant_regles"] == "1000.00"
    assert x["composantes_irg_avant_deductions"] == "1250.30"
    assert x["statut"] == "BASES_SIMULATION_DOCUMENTEES_NON_HOMOLOGUEES"
    assert x["bulletin_officiel_autorise"] is False
    assert [x["preuve_cnas"] for x in x["elements_qualifies"]] == [
        "CNAS-TEST","CNAS-TEST","CNAS-TEST"
    ]


def test_aucun_pourcentage_legal_implicite():
    x = audit([ligne(traitement_cnas="EXCLU",traitement_irg="EXCLU")])
    assert x["composantes_cnas_avant_regles"] == "0.00"
    assert x["composantes_irg_avant_deductions"] == "0.00"
    assert x["brut_reconstitue"] == "100.00"


@pytest.mark.parametrize("change", [
    {"montant":True},
    {"montant":10.23},
    {"montant":"NaN"},
    {"montant":"Infinity"},
    {"montant":"-1"},
    {"montant":"0"},
    {"montant":"0.001"},
    {"type_mouvement":"RETENUE"},
    {"type_mouvement":"RAPPEL_NON_CLASSE"},
    {"traitement_cnas":None},
    {"traitement_cnas":"9%"},
    {"traitement_irg":"EXONERE_AUTO"},
    {"preuve_cnas":None},
    {"preuve_irg":None},
    {"preuve_cnas":preuve() | {"source":""}},
    {"preuve_irg":preuve() | {"statut":"A_VERIFIER"}},
    {"preuve_cnas":preuve() | {"date_effet":"2027-01-01"}},
    {"preuve_irg":preuve() | {"date_fin":"2026-03-01"}},
    {"preuve_irg":preuve() | {"date_verification":"invalide"}},
    {"preuve_cnas":preuve() | {"date_fin":"2025-01-01"}},
    {"libelle":""},
    {"element_id":""},
])
def test_gain_ou_qualification_invalide_bloque(change):
    with pytest.raises(AssiettesNonDisponibles):
        audit([ligne(**change)])


def test_doublon_element_bloque():
    with pytest.raises(AssiettesNonDisponibles, match="dupliqué"):
        audit([ligne(), ligne()])


@pytest.mark.parametrize("value", [[], None, {}, "bad", [None], [ligne()] * 501])
def test_liste_invalide_bloque(value):
    with pytest.raises(AssiettesNonDisponibles):
        consolider_assiettes_paie(value, "2026-10-29")


@pytest.mark.parametrize("datevalue", ["2026-02-30", "2026-10-2", None])
def test_date_paie_invalide_bloque(datevalue):
    with pytest.raises(AssiettesNonDisponibles):
        consolider_assiettes_paie([ligne()], datevalue)


def test_ambiguites_de_preuve_non_appliquee_par_inference():
    x = audit([ligne(traitement_cnas="EXCLU",traitement_irg="INCLUS")])
    assert x["composantes_cnas_avant_regles"] == "0.00"
    assert x["composantes_irg_avant_deductions"] == "100.00"
    assert "assiette_irg" not in x
    assert "assiette_cnas" not in x


def test_hors_limite_cumulatif_rejete():
    with pytest.raises(AssiettesNonDisponibles, match="trop élevé"):
        audit([ligne("A","900000000000000"),ligne("B","900000000000000")])
