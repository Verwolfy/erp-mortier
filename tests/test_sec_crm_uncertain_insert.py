"""CRM : aucune réémission d'une création après une panne réseau.

Tous les scénarios sont hors réseau / hors PostgreSQL.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from modules.crm import service, views as crm
from tests.test_lot09_crm_lazy import PANELS, select, ui


def test_service_opportunity_uncertainty_preserves_attempted_reference(monkeypatch):
    monkeypatch.setattr(service, "get_pipeline", lambda: pd.DataFrame())
    calls = []

    def fail_insert(table, payload):
        calls.append((table, dict(payload)))
        raise RuntimeError("private-server-error")

    monkeypatch.setattr(service, "insert_hybrid", fail_insert)
    with pytest.raises(service.CRMCreationUncertain) as err:
        service.create_opportunite("Test", "", "Nouveau", "", 50.0, 30.0)
    assert len(calls) == 1
    assert calls[0][0] == "pipeline"
    assert err.value.document_id == calls[0][1]["opportunite_id"]
    assert err.value.document_id.startswith("OPP-")
    assert "private-server-error" not in str(err.value)


def test_service_interaction_uncertainty_preserves_attempted_reference(monkeypatch):
    calls = []

    def fail_insert(table, payload):
        calls.append((table, dict(payload)))
        raise RuntimeError("private-server-error")

    monkeypatch.setattr(service, "insert_hybrid", fail_insert)
    with pytest.raises(service.CRMCreationUncertain) as err:
        service.create_interaction("CLI-1", "Appel", "note", "")
    assert len(calls) == 1
    assert calls[0][0] == "interactions"
    assert err.value.document_id == calls[0][1]["interaction_id"]
    assert err.value.document_id.startswith("INT-")
    assert "private-server-error" not in str(err.value)


@pytest.mark.parametrize("kind", ["opportunite", "interaction"])
def test_one_attempt_confirmed_blocks_duplicate_write(ui, kind):
    st, *_ = ui
    write = MagicMock(return_value="CRM-OK")
    crm._crm_create_once(kind, "USR-CRM-T", write, "first-payload")
    assert write.call_count == 1
    assert st.session_state[crm._crm_creation_key(kind, "USR-CRM-T")] == {
        "status": "confirmed", "document_id": "CRM-OK",
    }
    st.success.assert_called_once()
    st.rerun.assert_called_once()
    crm._crm_create_once(kind, "USR-CRM-T", write, "same-payload")
    assert write.call_count == 1
    st.error.assert_called_once()


@pytest.mark.parametrize("kind", ["opportunite", "interaction"])
def test_uncertain_failure_keeps_document_id_and_never_retries(ui, kind):
    st, *_ = ui
    write = MagicMock(side_effect=service.CRMCreationUncertain("CRM-UNKNOWN"))
    crm._crm_create_once(kind, "USR-CRM-T", write, "payload")
    assert write.call_count == 1
    assert st.session_state[crm._crm_creation_key(kind, "USR-CRM-T")] == {
        "status": "uncertain", "document_id": "CRM-UNKNOWN",
    }
    assert "CRM-UNKNOWN" in str(st.code.call_args_list)
    assert "private" not in str(st.error.call_args)
    st.error.reset_mock()
    crm._crm_create_once(kind, "USR-CRM-T", write, "payload")
    assert write.call_count == 1
    st.error.assert_called_once()
    st.rerun.assert_not_called()


def test_plain_timeout_without_document_id_is_still_frozen(ui):
    st, *_ = ui
    write = MagicMock(side_effect=TimeoutError("private-timeout"))
    crm._crm_create_once("interaction", "USR-CRM-T", write, "payload")
    key = crm._crm_creation_key("interaction", "USR-CRM-T")
    assert st.session_state[key] == {"status": "uncertain", "document_id": None}
    assert "private-timeout" not in str(st.error.call_args)
    assert st.code.call_count == 0
    assert crm._crm_creation_guard("interaction", "USR-CRM-T") is False
    assert write.call_count == 1


def test_invalid_success_response_stays_uncertain_no_fake_confirmation(ui):
    st, *_ = ui
    write = MagicMock(return_value=None)
    crm._crm_create_once("opportunite", "USR-CRM-T", write, "payload")
    assert st.session_state[crm._crm_creation_key("opportunite", "USR-CRM-T")]["status"] == "uncertain"
    st.success.assert_not_called()
    st.rerun.assert_not_called()
    assert write.call_count == 1


def test_uncertain_guard_has_no_reset_control(ui):
    st, *_ = ui
    key = crm._crm_creation_key("opportunite", "USR-CRM-T")
    st.session_state[key] = {"status": "uncertain", "document_id": "OPP-TEST"}
    assert crm._crm_creation_guard("opportunite", "USR-CRM-T") is False
    st.error.assert_called_once()
    st.button.assert_not_called()
    assert st.session_state[key]["status"] == "uncertain"
    assert "OPP-TEST" in str(st.code.call_args)


def test_confirmed_guard_allows_explicit_new_creation(ui):
    st, *_ = ui
    key = crm._crm_creation_key("opportunite", "USR-CRM-T")
    st.session_state[key] = {"status": "confirmed", "document_id": "OPP-TEST"}
    st.button.return_value = True
    assert crm._crm_creation_guard("opportunite", "USR-CRM-T") is False
    assert key not in st.session_state
    st.rerun.assert_called_once()
    st.button.assert_called_once()
    assert st.button.call_args.kwargs["on_click"] is crm._mark_crm_activity


def test_corrupt_session_record_fails_closed(ui):
    st, *_ = ui
    key = crm._crm_creation_key("opportunite", "USR-CRM-T")
    st.session_state[key] = {"status": "other"}
    assert crm._crm_creation_guard("opportunite", "USR-CRM-T") is False
    st.button.assert_not_called()
    st.error.assert_called_once()


def test_pending_interaction_disables_form_and_client_reads(ui):
    st, _, pipe, clients, *_ = ui
    select(st, PANELS[1])
    st.session_state[crm._crm_creation_key("interaction", "USR-CRM-T")] = {
        "status": "uncertain", "document_id": "INT-TEST",
    }
    crm.show_crm_page()
    clients.assert_not_called()
    st.form.assert_not_called()
    st.form_submit_button.assert_not_called()
    st.error.assert_called_once()
    st.code.assert_called_once_with("INT-TEST")


def test_pending_opportunity_does_not_even_open_creation_expander(ui):
    st, _, pipe, *_ = ui
    select(st, PANELS[0])
    st.session_state[crm._crm_creation_key("opportunite", "USR-CRM-T")] = {
        "status": "uncertain", "document_id": "OPP-TEST",
    }
    crm.show_crm_page()
    st.expander.assert_not_called()
    st.form_submit_button.assert_not_called()
    pipe.assert_called_once()


def test_session_keys_isolate_user_and_creation_type(ui):
    st, *_ = ui
    keys = {crm._crm_creation_key(kind, user) for kind in ("opportunite", "interaction")
            for user in ("USER-A", "USER-B")}
    assert len(keys) == 4
    for key in keys:
        assert key not in st.session_state
    with pytest.raises(ValueError):
        crm._crm_creation_key("other", "USER-A")


def test_failed_preinsert_read_is_frozen_even_without_id(monkeypatch, ui):
    st, *_ = ui

    def cannot_read():
        raise RuntimeError("private-db-error")

    monkeypatch.setattr(service, "get_pipeline", cannot_read)
    # L'UI fige la tentative avant d'appeler le service métier.
    crm._crm_create_once("opportunite", "USR-CRM-T",
                         service.create_opportunite, "X", "", "Nouveau", "", 1.0, 50.0)
    assert st.session_state[crm._crm_creation_key("opportunite", "USR-CRM-T")]["status"] == "uncertain"
    assert "private-db-error" not in str(st.error.call_args)
