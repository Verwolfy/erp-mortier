"""Précontrôle en lecture seule : aucun résultat ne vaut facturation."""
from copy import deepcopy
from datetime import date, datetime
from unittest.mock import MagicMock

import pytest

from core import precontrole_exoneration_vente as app
from core.precontrole_exoneration_vente import (
    PrecontroleTVAIndisponible, verifier_exoneration_panier,
)

CERT = "00000000-0000-4000-8000-000000000031"
DATE = date(2026, 10, 29)


def reponse(statut="AUCUN_DOSSIER", motif="AUCUNE_PREUVE_ENREGISTREE"):
    base = {
        "statut": statut, "motif": motif, "autorise_facturation": False,
    }
    if statut == "PRECONTROLE_OK":
        base.update({
            "attestation_id": CERT,
            "reference_attestation": "TEST-EXONERATION",
            "date_validation": "2026-10-29",
            "nombre_sku": 2,
        })
    return base


@pytest.fixture
def rpc(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr(app, "get_supabase_client", lambda: db)
    monkeypatch.setattr(
        app, "get_local_now", lambda: datetime(2026, 10, 30, 15, 16)
    )
    return db


def appel():
    return verifier_exoneration_panier("CLI-TEST", ["SKU-X", "SKU-Y"], DATE)


def test_absence_dossier_ne_constitue_pas_une_exoneration(rpc):
    rpc.rpc.return_value.execute.return_value.data = reponse()
    result = appel()
    assert result == {
        "statut": "AUCUN_DOSSIER",
        "motif": "AUCUNE_PREUVE_ENREGISTREE",
        "autorise_facturation": False,
    }
    rpc.rpc.assert_called_once_with(
        "erp_exoneration_tva_precontrole_vente",
        {
            "p_client_id": "CLI-TEST",
            "p_sku_ids": ["SKU-X", "SKU-Y"],
            "p_date_facture": "2026-10-29",
        },
    )
    rpc.table.assert_not_called()


@pytest.mark.parametrize("motif", [
    "CLIENT_INACTIF_OU_INCONNU",
    "SKU_INACTIF_OU_INCONNU",
    "ATTESTATIONS_CONCURRENTES",
    "ATTESTATION_NON_HOMOLOGUEE",
    "PORTEE_SKU_PARTIELLE",
])
def test_refus_exonération_est_bloquant(rpc, motif):
    rpc.rpc.return_value.execute.return_value.data = reponse(
        "A_BLOQUER", motif
    )
    assert appel()["autorise_facturation"] is False
    assert appel()["statut"] == "A_BLOQUER"


def test_dossier_validé_reste_un_simple_precontrole(rpc):
    rpc.rpc.return_value.execute.return_value.data = reponse(
        "PRECONTROLE_OK", "ATTESTATION_ET_PORTEE_VERIFIEES"
    )
    result = appel()
    assert result["statut"] == "PRECONTROLE_OK"
    assert result["attestation_id"] == CERT
    assert result["nombre_sku"] == 2
    assert result["autorise_facturation"] is False


@pytest.mark.parametrize("response", [
    None, {}, [], "PRECONTROLE_OK",
    {"statut": "AUCUN_DOSSIER", "motif": "AUCUNE_PREUVE_ENREGISTREE",
     "autorise_facturation": True},
    {"statut": "PRECONTROLE_OK", "motif": "ATTESTATION_ET_PORTEE_VERIFIEES",
     "autorise_facturation": False},
    {"statut": "AUCUN_DOSSIER", "motif": "AUCUNE_PREUVE_ENREGISTREE",
     "autorise_facturation": False, "attestation_id": CERT},
])
def test_reponse_non_fiable_refusée(rpc, response):
    rpc.rpc.return_value.execute.return_value.data = response
    with pytest.raises(PrecontroleTVAIndisponible):
        appel()


@pytest.mark.parametrize("mutations", [
    {"attestation_id": "INVALID"},
    {"date_validation": "2026-10-30"},
    {"date_validation": "2026-13-01"},
    {"date_validation": None},
    {"nombre_sku": 3},
    {"reference_attestation": ""},
])
def test_preuve_de_validation_non_fiable_refusee(rpc, mutations):
    result = reponse("PRECONTROLE_OK", "ATTESTATION_ET_PORTEE_VERIFIEES")
    result.update(mutations)
    rpc.rpc.return_value.execute.return_value.data = result
    with pytest.raises(PrecontroleTVAIndisponible):
        appel()


@pytest.mark.parametrize("client,sku_ids,date_facture", [
    ("", ["SKU-X"], DATE),
    ("CLI-TEST", [], DATE),
    ("CLI-TEST", ["SKU-X", "SKU-X"], DATE),
    ("CLI-TEST", ["SKU-X", None], DATE),
    ("CLI-TEST", ["SKU-X"], date(2026, 11, 1)),
    ("CLI-TEST", ["SKU-X"], datetime(2026, 10, 29)),
    (None, ["SKU-X"], DATE),
])
def test_arguments_invalides_refuses_avant_appel_reseau(
    rpc, client, sku_ids, date_facture
):
    with pytest.raises(PrecontroleTVAIndisponible):
        verifier_exoneration_panier(client, sku_ids, date_facture)
    rpc.rpc.assert_not_called()


def test_resultat_est_filtre_et_independant_du_dictionnaire_sql(rpc):
    original = reponse("PRECONTROLE_OK", "ATTESTATION_ET_PORTEE_VERIFIEES")
    original["autorisation_inventee"] = "FACTURER_ZERO"
    rpc.rpc.return_value.execute.return_value.data = original
    out = appel()
    assert "autorisation_inventee" not in out
    avant = deepcopy(out)
    original["reference_attestation"] = "ALTEREE"
    assert out == avant


@pytest.mark.parametrize("champ,valeur", [
    ("statut", []),
    ("statut", {}),
    ("motif", []),
    ("motif", {}),
    ("motif", None),
])
def test_statut_ou_motif_non_textuel_refuse_proprement(rpc, champ, valeur):
    data = reponse()
    data[champ] = valeur
    rpc.rpc.return_value.execute.return_value.data = data
    with pytest.raises(PrecontroleTVAIndisponible, match="Statut fiscal"):
        appel()


@pytest.mark.parametrize("champ,valeur", [
    ("reference_attestation", "FAUSSE-PREUVE"),
    ("date_validation", "2026-10-29"),
    ("nombre_sku", 2),
])
def test_absence_dossier_avec_preuve_contradictoire_refusee(rpc, champ, valeur):
    data = reponse()
    data[champ] = valeur
    rpc.rpc.return_value.execute.return_value.data = data
    with pytest.raises(PrecontroleTVAIndisponible, match="Justificatif présent"):
        appel()


def test_nombre_sku_bool_n_est_pas_un_entier_valide(rpc):
    data = reponse("PRECONTROLE_OK", "ATTESTATION_ET_PORTEE_VERIFIEES")
    data["nombre_sku"] = True
    rpc.rpc.return_value.execute.return_value.data = data
    with pytest.raises(PrecontroleTVAIndisponible, match="Nombre de SKU"):
        verifier_exoneration_panier("CLI-TEST", ["SKU-X"], DATE)


@pytest.mark.parametrize("operation", ["rpc", "execute"])
def test_rpc_manquante_ou_non_autorisee_refusee(rpc, operation):
    if operation == "rpc":
        rpc.rpc.side_effect = RuntimeError("RPC manquante")
    else:
        rpc.rpc.return_value.execute.side_effect = PermissionError("42501")
    with pytest.raises(PrecontroleTVAIndisponible, match="indisponible"):
        appel()


@pytest.mark.parametrize("client,ids", [
    (" CLI-TEST", ["SKU-X"]),
    ("CLI-TEST ", ["SKU-X"]),
    ("CLI-TEST", [" SKU-X"]),
    ("CLI-TEST", ["SKU-X "]),
    ("CLI-TEST", ["A" * 201]),
    ("CLI-TEST", ["SKU-X", {"sku": "SKU-Y"}]),
    ("CLI-TEST", ["SKU-X", ["SKU-Y"]]),
])
def test_identifiants_mal_formes_bloquent_avant_reseau(rpc, client, ids):
    with pytest.raises(PrecontroleTVAIndisponible):
        verifier_exoneration_panier(client, ids, DATE)
    rpc.rpc.assert_not_called()
