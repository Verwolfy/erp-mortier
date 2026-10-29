"""Tests du registre TVA privé (sans appel réel à Supabase)."""
from unittest.mock import MagicMock

import pytest
from modules.admin import exonerations_service as service


def prepare(monkeypatch, entetes, portees, *, autorise=True):
    gate = MagicMock(return_value="USR-ADMIN")
    if not autorise:
        gate.side_effect = PermissionError("Manager requis")
    db = MagicMock()
    client = MagicMock(return_value=db)
    monkeypatch.setattr(service, "require_security_manager", gate)
    monkeypatch.setattr(service, "get_supabase_client", client)

    def table(name):
        obj = MagicMock()
        if name == "erp_exonerations_tva_clients":
            obj.select.return_value.order.return_value.range.return_value.execute.return_value.data = entetes
        elif name == "erp_exonerations_tva_skus":
            obj.select.return_value.order.return_value.range.return_value.execute.return_value.data = portees
        else:
            raise AssertionError("Table imprévue")
        return obj

    db.table.side_effect = table
    return gate, client, db


def attestation(id="AT-1"):
    return {
        "attestation_id": id,
        "client_id": "CLI-TEST",
        "reference_attestation": "DOC-TEST",
        "statut": "A_VALIDER",
    }


def test_refus_si_security_manager_non_confirme(monkeypatch):
    gate, client, db = prepare(monkeypatch, [], [], autorise=False)
    with pytest.raises(PermissionError):
        service.lister_attestations_pour_manager()
    gate.assert_called_once_with()
    client.assert_not_called()
    db.table.assert_not_called()


def test_tableau_regroupe_attestation_et_nombre_skus(monkeypatch):
    source = [attestation("AT-1"), attestation("AT-2")]
    gate, client, db = prepare(
        monkeypatch, source,
        [{"attestation_id": "AT-1", "sku_id": "SKU-A"},
         {"attestation_id": "AT-1", "sku_id": "SKU-B"}],
    )
    rows = service.lister_attestations_pour_manager()
    assert [r["nombre_sku_couverts"] for r in rows] == [2, 0]
    assert rows[0]["statut"] == "A_VALIDER"
    gate.assert_called_once_with()
    assert db.table.call_count == 2
    for call in db.table.call_args_list:
        assert call.args[0] in {
            "erp_exonerations_tva_clients", "erp_exonerations_tva_skus"
        }


def test_registre_vide_retourne_aucun_dossier(monkeypatch):
    _, _, db = prepare(monkeypatch, [], [])
    assert service.lister_attestations_pour_manager() == []
    db.table.assert_called_once_with("erp_exonerations_tva_clients")


@pytest.mark.parametrize("entetes,portees", [
    (None, []),
    ([None], []),
    ([attestation("AT-1"), attestation("AT-1")], []),
    ([attestation("AT-1")], None),
    ([attestation("AT-1")], [{"attestation_id": "AT-2", "sku_id": "SKU-X"}]),
    ([attestation("AT-1")], [{"attestation_id": "AT-1", "sku_id": ""}]),
    ([attestation("AT-1")], [None]),
])
def test_resultats_incomplets_refuses(monkeypatch, entetes, portees):
    prepare(monkeypatch, entetes, portees)
    with pytest.raises(RuntimeError):
        service.lister_attestations_pour_manager()


def test_limite_bloque_pagination_tronquee(monkeypatch):
    prepare(monkeypatch, [attestation("AT-%d" % i) for i in range(501)], [])
    with pytest.raises(RuntimeError, match="incomplète"):
        service.lister_attestations_pour_manager()


def payload_brouillon():
    return {
        "client_id": "CLI-X",
        "reference_attestation": "EXO-TEST",
        "autorite_emettrice": "AUTORITE-TEST",
        "reference_piece_interne": "PIECE-INTERNE",
        "justification": "A examiner",
        "date_effet": "2026-01-01",
        "date_fin": "2026-12-31",
        "sku_ids": ["SKU-001"],
    }


def test_creation_brouillon_appelle_rpc_protegee(monkeypatch):
    op_id = "00000000-0000-4000-8000-000000000027"
    attestation_id = "00000000-0000-4000-8000-000000000028"
    gate, client, db = prepare(monkeypatch, [], [])
    db.rpc.return_value.execute.return_value.data = {
        "operation_id": op_id, "action": "CREER_BROUILLON",
        "statut": "A_VALIDER", "attestation_id": attestation_id,
    }
    result = service.creer_brouillon_attestation(
        payload_brouillon(), operation_id=op_id
    )
    assert result == attestation_id
    gate.assert_called_once_with()
    db.rpc.assert_called_once_with(
        "erp_exoneration_tva_action", {
            "p_actor_id": "USR-ADMIN", "p_action": "CREER_BROUILLON",
            "p_operation_id": op_id, "p_payload": payload_brouillon(),
        }
    )
    db.table.assert_not_called()


def test_creation_brouillon_refuse_utilisateur_sans_droit(monkeypatch):
    gate, client, db = prepare(monkeypatch, [], [], autorise=False)
    with pytest.raises(PermissionError):
        service.creer_brouillon_attestation(
            payload_brouillon(), operation_id="00000000-0000-4000-8000-000000000027"
        )
    client.assert_not_called()


@pytest.mark.parametrize("mutation", [
    {"sku_ids": []}, {"sku_ids": ["SKU-001", "SKU-001"]},
    {"date_effet": "2026-13-01"}, {"date_fin": "2025-01-01"},
    {"reference_piece_interne": ""}, {"client_id": None},
    {"statut": "VALIDEE"},
])
def test_creation_brouillon_invalide_ne_touche_pas_rpc(monkeypatch, mutation):
    gate, client, db = prepare(monkeypatch, [], [])
    donnees = payload_brouillon()
    donnees.update(mutation)
    with pytest.raises(ValueError):
        service.creer_brouillon_attestation(
            donnees, operation_id="00000000-0000-4000-8000-000000000027"
        )
    gate.assert_not_called()
    client.assert_not_called()


@pytest.mark.parametrize("reponse", [
    None, {}, {"action": "VALIDER"},
    {"operation_id": "autre", "action": "CREER_BROUILLON",
     "statut": "A_VALIDER", "attestation_id": "00000000-0000-4000-8000-000000000028"},
])
def test_reponse_sql_non_confirmee_refusee(monkeypatch, reponse):
    _, _, db = prepare(monkeypatch, [], [])
    db.rpc.return_value.execute.return_value.data = reponse
    with pytest.raises(RuntimeError):
        service.creer_brouillon_attestation(
            payload_brouillon(), operation_id="00000000-0000-4000-8000-000000000027"
        )


def test_statut_validateur_fiscal_lit_habilitation_serveur(monkeypatch):
    gate, _, db = prepare(monkeypatch, [], [])
    db.rpc.return_value.execute.return_value.data = False
    assert service.est_validateur_fiscal() is False
    gate.assert_called_once_with()
    db.rpc.assert_called_once_with(
        "erp_exoneration_tva_is_validator", {"p_actor_id": "USR-ADMIN"}
    )


@pytest.mark.parametrize("valeur", [None, {}, [], 1, "true"])
def test_habilitation_fiscale_non_bool_refusee(monkeypatch, valeur):
    _, _, db = prepare(monkeypatch, [], [])
    db.rpc.return_value.execute.return_value.data = valeur
    with pytest.raises(RuntimeError, match="non vérifiable"):
        service.est_validateur_fiscal()


def _rpc_replies(permission, reply):
    def call(name, args):
        result = MagicMock()
        if name == "erp_exoneration_tva_is_validator":
            result.execute.return_value.data = permission
        elif name == "erp_exoneration_tva_action":
            result.execute.return_value.data = reply
        else:
            raise AssertionError("RPC imprévue")
        return result
    return call


@pytest.mark.parametrize("action,justification,status", [
    ("VALIDER", {
        "verification_documentaire": True,
        "date_verification": "2026-10-29",
        "reference_avis_validation": "AVIS-TEST"
    }, "VALIDEE"),
    ("REVOQUER", {
        "motif_revocation": "Avis retiré après contrôle"
    }, "REVOQUEE"),
])
def test_transition_attestation_protegee(monkeypatch, action, justification, status):
    attestation = "00000000-0000-4000-8000-000000000028"
    operation = "00000000-0000-4000-8000-000000000029"
    gate, _, db = prepare(monkeypatch, [], [])
    reply = {
        "operation_id": operation, "attestation_id": attestation,
        "action": action, "statut": status, "idempotent": False,
    }
    db.rpc.side_effect = _rpc_replies(True, reply)
    assert service.transition_attestation(
        action, attestation_id=attestation,
        operation_id=operation, justification=justification
    ) == attestation
    gate.assert_called_once_with()
    assert db.rpc.call_count == 2
    assert db.rpc.call_args_list[0].args[0] == "erp_exoneration_tva_is_validator"
    assert db.rpc.call_args_list[1].args == (
        "erp_exoneration_tva_action", {
            "p_actor_id": "USR-ADMIN", "p_action": action,
            "p_operation_id": operation,
            "p_payload": {**justification, "attestation_id": attestation},
        }
    )


@pytest.mark.parametrize("permission", [False, None, "true", 1, {}])
def test_decision_refusee_sans_validation_fiscale_fraiche(monkeypatch, permission):
    _, _, db = prepare(monkeypatch, [], [])
    db.rpc.side_effect = _rpc_replies(permission, {})
    with pytest.raises(PermissionError, match="non habilité"):
        service.transition_attestation(
            "REVOQUER",
            attestation_id="00000000-0000-4000-8000-000000000028",
            operation_id="00000000-0000-4000-8000-000000000029",
            justification={"motif_revocation": "Test"},
        )
    assert db.rpc.call_count == 1


@pytest.mark.parametrize("action,justification", [
    ("INCONNU", {}),
    ("VALIDER", {"verification_documentaire": False,
                  "date_verification": "2026-10-29",
                  "reference_avis_validation": "AVIS-TEST"}),
    ("VALIDER", {"verification_documentaire": True,
                  "date_verification": "2026-13-29",
                  "reference_avis_validation": "AVIS-TEST"}),
    ("VALIDER", {"verification_documentaire": True,
                  "date_verification": "2026-10-29",
                  "reference_avis_validation": ""}),
    ("REVOQUER", {"motif_revocation": ""}),
    ("REVOQUER", {"motif_revocation": "raison", "statut": "VALIDEE"}),
])
def test_transition_invalide_ne_touche_ni_autorisation_ni_rpc(
    monkeypatch, action, justification
):
    gate, client, db = prepare(monkeypatch, [], [])
    with pytest.raises(ValueError):
        service.transition_attestation(
            action, attestation_id="00000000-0000-4000-8000-000000000028",
            operation_id="00000000-0000-4000-8000-000000000029",
            justification=justification,
        )
    gate.assert_not_called()
    client.assert_not_called()


def test_reponse_transition_non_confirmee_refusee(monkeypatch):
    _, _, db = prepare(monkeypatch, [], [])
    db.rpc.side_effect = _rpc_replies(True, {
        "operation_id": "00000000-0000-4000-8000-000000000029",
        "attestation_id": "00000000-0000-4000-8000-000000000028",
        "action": "VALIDER", "statut": "REVOQUEE",
    })
    with pytest.raises(RuntimeError, match="non confirmée"):
        service.transition_attestation(
            "VALIDER", attestation_id="00000000-0000-4000-8000-000000000028",
            operation_id="00000000-0000-4000-8000-000000000029",
            justification={"verification_documentaire": True,
                "date_verification": "2026-10-29",
                "reference_avis_validation": "AVIS-TEST"}
        )
