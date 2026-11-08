"""SEC-CRM-03 : tests hors réseau du contrat FUTUR de RPC idempotente.

Ces tests ne prouvent PAS l'exécution SQL ni sa concurrence en PostgreSQL.
Les tests de transactions doivent être faits ensuite sur Supabase TEST isolé.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from modules.crm.idempotency_contract import (
    CRMResponseUncertain,
    build_rpc_request,
    require_rpc_confirmation,
)


ROOT = Path(__file__).resolve().parents[1]
DRAFT = ROOT / "sql" / "supabase_pending" / (
    "erp_035_crm_idempotence_CANDIDAT_NON_EXECUTE.sql"
)
OPPORTUNITY = {
    "prospect_nom": "Prospect de test",
    "contact": "",
    "statut": "Nouveau",
    "commercial_id": "",
    "valeur_estimee": 1500,
    "probabilite_pct": 50,
}
INTERACTION = {
    "client_id": "CLIENT-TEST",
    "type_action": "Appel",
    "notes": "Note fictive pour test",
    "date_rappel": "",
}


@pytest.mark.parametrize("kind,payload", [
    ("opportunite", OPPORTUNITY),
    ("interaction", INTERACTION),
])
def test_create_stable_operation_request_without_mutating_original(kind, payload):
    initial = dict(payload)
    result = build_rpc_request(kind, "USR-TEST", payload)
    UUID(result["p_operation_id"])
    assert result["p_kind"] == kind
    assert result["p_actor_id"] == "USR-TEST"
    assert result["p_payload"] == initial
    assert result["p_payload"] is not payload
    assert payload == initial
    assert build_rpc_request(
        kind, "USR-TEST", initial,
        operation_id=result["p_operation_id"]
    ) == result


@pytest.mark.parametrize("kind,payload", [
    ("opportunite", OPPORTUNITY),
    ("interaction", INTERACTION),
])
def test_distinct_requests_get_distinct_uuids(kind, payload):
    x = build_rpc_request(kind, "USR-TEST", payload)
    y = build_rpc_request(kind, "USR-TEST", payload)
    assert x["p_operation_id"] != y["p_operation_id"]


@pytest.mark.parametrize("bad_kind,bad_user,bad_payload", [
    ("other", "USR-TEST", OPPORTUNITY),
    ("opportunite", "", OPPORTUNITY),
    ("opportunite", " " * 2, OPPORTUNITY),
    ("opportunite", "X" * 129, OPPORTUNITY),
    ("interaction", "USR-TEST", []),
    ("interaction", "USR-TEST", OPPORTUNITY),
])
def test_request_rejects_invalid_kind_actor_or_fields(bad_kind, bad_user, bad_payload):
    with pytest.raises(ValueError):
        build_rpc_request(bad_kind, bad_user, bad_payload)


@pytest.mark.parametrize("changed", [
    {"statut": "AUTRE"}, {"statut": []}, {"prospect_nom": ""},
    {"contact": None}, {"commercial_id": None},
    {"valeur_estimee": -1}, {"valeur_estimee": float("nan")},
    {"valeur_estimee": True}, {"probabilite_pct": 101},
    {"probabilite_pct": "50"}, {"contact": "X" * 401},
])
def test_opportunity_validation_rejects_bad_payload(changed):
    payload = dict(OPPORTUNITY, **changed)
    with pytest.raises(ValueError):
        build_rpc_request("opportunite", "USR-TEST", payload)


@pytest.mark.parametrize("changed", [
    {"client_id": ""}, {"type_action": ""}, {"notes": None},
    {"notes": "X" * 4001}, {"date_rappel": "2026-02-31"},
    {"date_rappel": "2026-2-1"}, {"date_rappel": None},
])
def test_interaction_validation_rejects_bad_payload(changed):
    payload = dict(INTERACTION, **changed)
    with pytest.raises(ValueError):
        build_rpc_request("interaction", "USR-TEST", payload)


@pytest.mark.parametrize("invalid", [
    "", "not-a-uuid", "00000000-0000-0000-0000-000000000000extra",
    "D53F1D9E-8C2E-497A-9E8A-1570F2A3600B", 1234,
])
def test_rejects_noncanonical_uuid(invalid):
    with pytest.raises(ValueError):
        build_rpc_request("opportunite", "USR-TEST", OPPORTUNITY,
                          operation_id=invalid)


@pytest.mark.parametrize("kind,payload,prefix", [
    ("opportunite", OPPORTUNITY, "OPP-"),
    ("interaction", INTERACTION, "INT-"),
])
def test_valid_first_and_replayed_response_same_document(kind, payload, prefix):
    req = build_rpc_request(kind, "USR-TEST", payload)
    document = prefix + "A" * 32
    for is_replay in (False, True):
        response = SimpleNamespace(data={
            "operation_id": req["p_operation_id"], "kind": kind,
            "document_id": document, "replayed": is_replay,
        })
        assert require_rpc_confirmation(response, req) == document


@pytest.mark.parametrize("override", [
    {"operation_id": "WRONG"}, {"kind": "interaction"},
    {"document_id": "OPP-INVALID"}, {"document_id": "INT-" + "A" * 32},
    {"document_id": "OPP-" + "Z" * 32}, {"replayed": "yes"},
    {"replayed": None},
])
def test_unknown_or_conflicting_rpc_receipt_is_uncertain(override):
    req = build_rpc_request("opportunite", "USR-TEST", OPPORTUNITY)
    data = {
        "operation_id": req["p_operation_id"],
        "kind": "opportunite",
        "document_id": "OPP-" + "A" * 32,
        "replayed": False,
    }
    data.update(override)
    with pytest.raises(CRMResponseUncertain) as err:
        require_rpc_confirmation(SimpleNamespace(data=data), req)
    assert err.value.operation_id == req["p_operation_id"]


@pytest.mark.parametrize("response", [
    None, SimpleNamespace(data=None), SimpleNamespace(data=[]),
    SimpleNamespace(data={}), SimpleNamespace(data="private"),
])
def test_absent_response_never_triggers_another_request(response):
    req = build_rpc_request("opportunite", "USR-TEST", OPPORTUNITY)
    with pytest.raises(CRMResponseUncertain) as err:
        require_rpc_confirmation(response, req)
    assert err.value.operation_id == req["p_operation_id"]
    assert "private" not in str(err.value)


def test_sql_is_staged_non_executed_with_private_registry_and_atomic_rpc():
    source = DRAFT.read_text(encoding="utf-8")
    assert "CANDIDAT POUR TEST ISOLE UNIQUEMENT" in source
    assert "NE JAMAIS EXECUTER" in source
    assert source.count("BEGIN;") == source.count("COMMIT;") == 1
    assert "CREATE SCHEMA IF NOT EXISTS erp_crm_private;" in source
    assert "CREATE TABLE IF NOT EXISTS erp_crm_private.operation_receipts" in source
    assert "operation_id uuid PRIMARY KEY" in source
    assert "UNIQUE (kind, document_id)" in source
    assert "ENABLE ROW LEVEL SECURITY" in source
    assert "SECURITY DEFINER" in source
    assert "SET search_path = ''" in source
    assert "ON CONFLICT (operation_id) DO NOTHING" in source
    assert "FOR UPDATE" in source
    assert "v_receipt.request_payload <> p_payload" in source
    assert "v_receipt.actor_id <> p_actor_id" in source
    assert "CRM_OPERATION_CONFLICT" in source
    assert "v_new := FOUND" in source
    assert "IF v_new THEN" in source
    assert "CRM_RECEIPT_ORPHAN" in source
    assert "jsonb_build_object(" in source
    assert "'replayed', NOT v_new" in source
    assert "DROP TABLE" not in source
    assert "TRUNCATE " not in source
    assert "DELETE FROM public." not in source


def test_sql_revalidates_current_server_rights_on_every_call():
    source = DRAFT.read_text(encoding="utf-8")
    pos_access = source.index("FROM public.users")
    pos_permissions = source.index("FROM public.permissions")
    pos_reg = source.index("INSERT INTO erp_crm_private.operation_receipts")
    assert pos_access < pos_permissions < pos_reg
    assert "FROM public.users" in source
    assert "FOR SHARE" in source
    assert "v_perm_count <> 1" in source
    assert "CRM_ACCESS_DENIED" in source
    assert "p_kind NOT IN ('opportunite', 'interaction')" in source
    assert "jsonb_typeof(p_payload->'notes') IS DISTINCT FROM 'string'" in source
    assert "CRM_CLIENT_UNAVAILABLE" in source
    assert "PERFORM 1 FROM public.permissions AS p" in source
    assert "!~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' OR" in source
    assert "public.pipeline" in source
    assert "public.interactions" in source


def test_sql_rpc_is_granted_only_to_backend_service_role():
    source = DRAFT.read_text(encoding="utf-8")
    assert ("REVOKE ALL ON FUNCTION "
            "public.erp_crm_create_idempotent(uuid,text,text,jsonb)") in source
    assert "FROM PUBLIC, anon, authenticated;" in source
    assert ("GRANT EXECUTE ON FUNCTION "
            "public.erp_crm_create_idempotent(uuid,text,text,jsonb)") in source
    assert "TO service_role;" in source
    assert "GRANT EXECUTE" in source
    assert "TO authenticated;" not in source
    assert "TO anon;" not in source
    assert "auth.role()" not in source


def test_existing_crm_path_not_switched_to_untested_rpc():
    service_source = (
        ROOT / "modules" / "crm" / "service.py"
    ).read_text(encoding="utf-8")
    assert 'insert_hybrid("pipeline", data_opp)' in service_source
    assert 'insert_hybrid("interactions", data_int)' in service_source
    assert "erp_crm_create_idempotent" not in service_source
