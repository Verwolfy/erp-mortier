"""Tests de reconstruction d'attestations : données synthétiques sans I/O."""
from copy import deepcopy
from datetime import date

import pytest

from core.fiscalite_facturation import FiscaliteNonDisponible
from core.lecture_exonerations_tva_clients import selectionner_attestation_client

A = "00000000-0000-4000-8000-000000000001"
B = "00000000-0000-4000-8000-000000000002"


def dossier(*, attestation_id=A, client_id="CLI-X", statut="VALIDEE"):
    return {
        "attestation_id": attestation_id, "client_id": client_id,
        "reference_attestation": "DOC-FICTIF-01",
        "autorite_emettrice": "AUTORITE-TEST", "reference_piece_interne": "INTERNE-TEST",
        "justification": "TEST", "statut": statut,
        "date_effet": "2026-01-01", "date_fin": "2026-12-31",
        "date_verification": "2026-01-02", "date_validation": "2026-01-03",
        "valide_par": "VALIDATEUR-TEST",
    }


def ligne(sku="SKU-X", attestation_id=A):
    return {"attestation_id": attestation_id, "sku_id": sku}


def lecture(entetes=None, portees=None, *, jour=date(2026, 3, 15)):
    return selectionner_attestation_client(
        "CLI-X", jour,
        [dossier()] if entetes is None else entetes,
        [ligne()] if portees is None else portees,
    )


def test_dossier_et_portee_reconstruits_sans_mutation():
    dossiers, portees = [dossier()], [ligne(), ligne("SKU-Y")]
    original = deepcopy((dossiers, portees))
    preuve = lecture(dossiers, portees)
    assert preuve["client_id"] == "CLI-X"
    assert preuve["attestation_id"] == A
    assert preuve["sku_ids_couverts"] == ("SKU-X", "SKU-Y")
    assert preuve["reference_piece_interne"] == "INTERNE-TEST"
    assert (dossiers, portees) == original


def test_absence_dossier_applicable_ne_presume_pas_exoneration():
    assert lecture([], []) is None
    assert lecture([dossier()], [ligne()], jour=date(2027, 1, 1)) is None


@pytest.mark.parametrize("etat", ["A_VALIDER", "REVOQUEE", "INCONNU"])
def test_dossier_non_valide_est_bloquant(etat):
    with pytest.raises(FiscaliteNonDisponible, match="non validée"):
        lecture([dossier(statut=etat)])


def test_dossiers_concurrents_bloquent_meme_si_valides():
    with pytest.raises(FiscaliteNonDisponible, match="concurrentes"):
        lecture([dossier(), dossier(attestation_id=B)],
               [ligne(), ligne("SKU-Y", B)])


@pytest.mark.parametrize("entetes,portees", [
    ([dossier()], []),
    ([dossier()], [ligne(), ligne()]),
    ([dossier()], [ligne(sku="")]),
    ([dossier()], [ligne(attestation_id="pas-uuid")]),
    ([dossier(), dossier()], [ligne()]),
    ([dossier(attestation_id="pas-uuid")], [ligne()]),
])
def test_donnees_ambigues_ou_invalides_refusees(entetes, portees):
    with pytest.raises(FiscaliteNonDisponible):
        lecture(entetes, portees)


def test_reference_piece_absente_bloque():
    d = dossier()
    d["reference_piece_interne"] = None
    with pytest.raises(FiscaliteNonDisponible, match="Référence de pièce"):
        lecture([d])


def test_autre_client_n_accorde_pas_exoneration():
    assert lecture([dossier(client_id="CLI-AUTRE")], [ligne()]) is None


def test_attestation_validee_apres_facture_refusee():
    d = dossier()
    d["date_validation"] = "2026-05-01"
    d["date_verification"] = "2026-04-30"
    with pytest.raises(FiscaliteNonDisponible):
        lecture([d])
