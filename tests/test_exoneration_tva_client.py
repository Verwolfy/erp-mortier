"""Vérification client exonéré, sans accès aux données ni hypothèse légale."""
from copy import deepcopy
from datetime import date

import pytest

from core.exoneration_tva_client import qualifier_exoneration_client
from core.fiscalite_facturation import FiscaliteNonDisponible


def attestation():
    return {
        "client_id": "CLI-TEST", "statut": "VALIDEE",
        "date_effet": "2026-01-01", "date_fin": "2026-12-31",
        "date_verification": "2026-01-02",
        "date_validation": "2026-01-03",
        "reference_attestation": "ATTESTATION-FICTIVE",
        "autorite_emettrice": "AUTORITE-FICTIVE",
        "valide_par": "VALIDATEUR-FICTIF",
        "justification": "PORTÉE-TEST",
        "sku_ids_couverts": ["SKU-A", "SKU-B"],
    }


def test_aucune_attestation_ne_produit_aucune_exoneration():
    assert qualifier_exoneration_client(None, date(2026, 2, 1), None) is None


def test_attestation_validee_produit_preuve_datee_et_portee():
    source = attestation()
    sortie = qualifier_exoneration_client("CLI-TEST", date(2026, 2, 1), source)
    assert sortie["client_id"] == "CLI-TEST"
    assert sortie["sku_ids_couverts"] == ("SKU-A", "SKU-B")
    assert sortie["date_fin"] == "2026-12-31"
    assert sortie["reference_attestation"] == "ATTESTATION-FICTIVE"
    source["sku_ids_couverts"].append("SKU-C")
    source["reference_attestation"] = "ALTÉRÉE"
    assert sortie["sku_ids_couverts"] == ("SKU-A", "SKU-B")
    assert sortie["reference_attestation"] == "ATTESTATION-FICTIVE"


@pytest.mark.parametrize("champ,valeur", [
    ("client_id", "CLI-AUTRE"), ("statut", "A_VALIDER"),
    ("date_effet", "2026-03-01"), ("date_fin", "2026-01-31"),
    ("date_verification", "2026-02-03"), ("date_validation", "2026-02-02"),
    ("reference_attestation", ""), ("autorite_emettrice", None),
    ("valide_par", ""), ("justification", ""),
    ("sku_ids_couverts", []), ("sku_ids_couverts", ["SKU-A", "SKU-A"]),
    ("sku_ids_couverts", ["SKU-A", None]),
])
def test_attestation_non_eligible_refusee(champ, valeur):
    source = attestation()
    source[champ] = valeur
    with pytest.raises(FiscaliteNonDisponible):
        qualifier_exoneration_client("CLI-TEST", date(2026, 2, 1), source)


def test_expiration_refusee_sans_retour_silencieux_au_taux_normal():
    with pytest.raises(FiscaliteNonDisponible, match="non applicable"):
        qualifier_exoneration_client("CLI-TEST", date(2027, 1, 1), attestation())


def test_une_attestation_sans_identite_client_est_refusee():
    with pytest.raises(FiscaliteNonDisponible):
        qualifier_exoneration_client(None, date(2026, 2, 1), attestation())


def test_incoherence_dates_inversee_refusee():
    source = attestation()
    source["date_fin"] = "2025-12-31"
    with pytest.raises(FiscaliteNonDisponible):
        qualifier_exoneration_client("CLI-TEST", date(2026, 2, 1), source)
