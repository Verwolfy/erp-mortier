"""SEC-CRM : la session n'accorde jamais de droit sans relecture Supabase.

Tests isolés, sans accès réseau, données réelles ni mutation PostgreSQL.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest

from modules.crm import views as crm
from tests.test_lot09_crm_lazy import PANELS, select, ui


def _response(ui, rows):
    client = crm.get_supabase_client.return_value
    query = client.table.return_value.select.return_value.eq.return_value.limit.return_value
    query.execute.return_value = SimpleNamespace(data=rows)
    return client, query


def _actor(role="ADMIN", actif="OUI", user_id="USR-CRM-T"):
    return {"user_id": user_id, "role": role, "actif": actif}


@pytest.mark.parametrize("invalid", [
    [], [_actor(), _actor()], [{"user_id": "OTHER", "role": "ADMIN", "actif": "OUI"}],
    [_actor(actif="NON")], [_actor(actif=False)], [_actor(actif=None)],
    [_actor(actif=1)], [_actor(role="")], [_actor(role=None)],
    [{"user_id": "USR-CRM-T", "role": "ADMIN"}], [None], {"bad": "shape"},
])
def test_invalid_database_account_denies_access_before_navigation(ui, invalid):
    st, _, pipe, clients, inbox, requests = ui
    client, query = _response(ui, invalid)
    crm.show_crm_page()
    st.selectbox.assert_not_called()
    pipe.assert_not_called()
    clients.assert_not_called()
    inbox.assert_not_called()
    requests.assert_not_called()
    st.error.assert_called_once_with(
        "Accès CRM refusé : compte ou droits non vérifiables.")
    client.table.assert_called_once_with("users")
    client.table.return_value.select.assert_called_once_with("user_id,role,actif")
    client.table.return_value.select.return_value.eq.assert_called_once_with(
        "user_id", "USR-CRM-T")
    client.table.return_value.select.return_value.eq.return_value.limit.assert_called_once_with(2)


@pytest.mark.parametrize("logged,user", [
    (False, {"user_id": "USR-CRM-T", "role": "ADMIN"}),
    ("yes", {"user_id": "USR-CRM-T", "role": "ADMIN"}),
    (True, None), (True, {}), (True, {"role": "ADMIN"}),
    (True, {"user_id": 5, "role": "ADMIN"}),
    (True, {"user_id": " ", "role": "ADMIN"}),
])
def test_unverified_session_never_queries_database(ui, logged, user):
    st, perm, pipe, clients, inbox, requests = ui
    st.session_state["authenticated"] = logged
    st.session_state["user"] = user
    crm.show_crm_page()
    crm.get_supabase_client.assert_not_called()
    perm.assert_not_called()
    st.selectbox.assert_not_called()
    pipe.assert_not_called()


def test_backend_failure_is_fail_closed_without_sensitive_message(ui):
    st, perm, pipe, *_ = ui
    crm.get_supabase_client.side_effect = RuntimeError("PRIVATE-DB-DETAIL")
    crm.show_crm_page()
    st.selectbox.assert_not_called()
    pipe.assert_not_called()
    perm.assert_not_called()
    st.error.assert_called_once()
    assert "PRIVATE-DB-DETAIL" not in str(st.error.call_args)


def test_server_role_overrides_session_admin_for_read_only(ui):
    st, perm, pipe, clients, inbox, requests = ui
    _response(ui, [_actor(role="LECTEUR_CRM")])
    perm.side_effect = lambda role, module, action: (
        role == "LECTEUR_CRM" and module == "CRM" and action == "lecture"
    )
    select(st, PANELS[1])
    crm.show_crm_page()
    assert perm.call_args_list[0].args == ("LECTEUR_CRM", "CRM", "lecture")
    assert perm.call_args_list[1].args == ("LECTEUR_CRM", "CRM", "ecriture")
    clients.assert_not_called()
    st.form.assert_not_called()
    st.selectbox.assert_called_once()
    assert st.selectbox.call_args.args[0] == "Vue CRM"


def test_revoked_server_read_permission_blocks_even_admin_session(ui):
    st, perm, pipe, clients, inbox, requests = ui
    _response(ui, [_actor(role="REVOQUE")])
    perm.side_effect = lambda role, module, action: False
    crm.show_crm_page()
    perm.assert_called_once_with("REVOQUE", "CRM", "lecture")
    st.selectbox.assert_not_called()
    pipe.assert_not_called()
    clients.assert_not_called()


def test_fresh_access_is_not_cached_between_renders(ui):
    st, perm, pipe, *_ = ui
    client, query = _response(ui, [_actor()])
    crm.show_crm_page()
    query.execute.return_value = SimpleNamespace(data=[_actor(actif="NON")])
    crm.show_crm_page()
    assert query.execute.call_count == 2
    assert pipe.call_count == 1
    st.error.assert_called_once()
    assert client.table.call_count == 2


def test_opportunity_creation_rechecks_revocation_at_submit(ui, monkeypatch):
    st, perm, pipe, *_ = ui
    client, query = _response(ui, [_actor()])
    query.execute.side_effect = [
        SimpleNamespace(data=[_actor()]),
        SimpleNamespace(data=[_actor(actif="NON")]),
    ]
    select(st, PANELS[0])
    st.form_submit_button.return_value = True
    monkeypatch.setattr(crm, "create_opportunite", MagicMock())
    crm.show_crm_page()
    assert query.execute.call_count == 2
    crm.create_opportunite.assert_not_called()
    st.success.assert_not_called()
    assert any("révoqué" in c.args[0] for c in st.error.call_args_list)


def test_interaction_creation_rechecks_revocation_at_submit(ui, monkeypatch):
    st, perm, pipe, clients, *_ = ui
    client, query = _response(ui, [_actor()])
    query.execute.side_effect = [
        SimpleNamespace(data=[_actor()]),
        SimpleNamespace(data=[_actor(role="LECTEUR_CRM")]),
    ]
    perm.side_effect = lambda role, module, action: (
        role == "ADMIN" or (role == "LECTEUR_CRM" and action == "lecture")
    )
    select(st, PANELS[1])
    st.form_submit_button.return_value = True
    clients.return_value = pd.DataFrame([{
        "client_id": "CLI-TEST", "nom": "Démonstration", "actif": "OUI"
    }])
    monkeypatch.setattr(crm, "get_liste", lambda *_a, **_kw: [])
    monkeypatch.setattr(crm, "liste_to_dict", lambda *_a: {})
    monkeypatch.setattr(crm, "create_interaction", MagicMock())
    crm.show_crm_page()
    assert query.execute.call_count == 2
    crm.create_interaction.assert_not_called()
    st.success.assert_not_called()
    assert any("révoqué" in c.args[0] for c in st.error.call_args_list)


def test_identity_changed_while_submitting_blocks_write(ui, monkeypatch):
    st, _, pipe, *_ = ui
    select(st, PANELS[0])
    st.form_submit_button.return_value = True
    monkeypatch.setattr(crm, "_crm_access",
                        MagicMock(side_effect=[("USR-CRM-T", True),
                                               ("USR-OTHER", True)]))
    monkeypatch.setattr(crm, "create_opportunite", MagicMock())
    crm.show_crm_page()
    crm.create_opportunite.assert_not_called()
    st.success.assert_not_called()
    assert any("révoqué" in c.args[0] for c in st.error.call_args_list)


def test_authorized_create_still_calls_original_service_once(ui, monkeypatch):
    st, _, pipe, *_ = ui
    select(st, PANELS[0])
    st.form_submit_button.return_value = True
    st.columns.side_effect = lambda count: [
        MagicMock() for _ in range(count)
    ]
    monkeypatch.setattr(crm, "_crm_access",
                        MagicMock(return_value=("USR-CRM-T", True)))
    write = MagicMock(return_value="OPP-TEST")
    monkeypatch.setattr(crm, "create_opportunite", write)
    crm.show_crm_page()
    write.assert_called_once()
    st.success.assert_called_once()
