"""Lot 09 CRM : une seule vue exécutée, sans fuite entre panneaux."""
from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest
from modules.crm import views as crm


PANELS = (
    "🎯 Pipeline (Opportunités)", "📞 Consigner une interaction",
    "📋 Historique des échanges", "🌐 Demandes NextGen",
)


@pytest.fixture
def ui(monkeypatch):
    st = MagicMock()
    st.session_state = {
        "authenticated": True, "user": {"user_id": "USR-CRM-T", "role": "ADMIN"},
    }
    st.form_submit_button.return_value = False
    st.button.return_value = False
    st.selectbox.side_effect = lambda _label, options, **_kw: list(options)[0]
    st.number_input.return_value = 1
    st.columns.side_effect = lambda count: [
        MagicMock() for _ in range(count if isinstance(count, int) else len(count))
    ]
    monkeypatch.setattr(crm, "st", st)
    client = MagicMock()
    (client.table.return_value.select.return_value.eq.return_value
           .limit.return_value.execute.return_value) = SimpleNamespace(
               data=[{"user_id": "USR-CRM-T", "role": "ADMIN", "actif": "OUI"}]
           )
    monkeypatch.setattr(crm, "get_supabase_client",
                        MagicMock(return_value=client))
    perm = MagicMock(return_value=True)
    monkeypatch.setattr(crm, "has_permission", perm)
    pipe = MagicMock(return_value=pd.DataFrame())
    clients = MagicMock(return_value=pd.DataFrame())
    inbox = MagicMock(return_value=False)
    requests = MagicMock(return_value=([], False))
    monkeypatch.setattr(crm, "get_pipeline", pipe)
    monkeypatch.setattr(crm, "get_clients_actifs", clients)
    monkeypatch.setattr(crm, "inbox_enabled", inbox)
    monkeypatch.setattr(crm, "list_requests_readonly", requests)
    monkeypatch.setattr(crm, "read_section", lambda _label: nullcontext())
    return st, perm, pipe, clients, inbox, requests


def select(st, panel):
    st.selectbox.side_effect = (
        lambda label, options, **_kw:
        panel if label == "Vue CRM" else list(options)[0]
    )


def test_pipeline_does_not_read_clients_or_site_inbox(ui):
    st, _, pipe, clients, inbox, requests = ui
    select(st, PANELS[0])
    crm.show_crm_page()
    pipe.assert_called_once()
    clients.assert_not_called()
    inbox.assert_not_called()
    requests.assert_not_called()
    st.tabs.assert_not_called()


def test_interactions_does_not_read_pipeline_or_site_inbox(ui):
    st, _, pipe, clients, inbox, requests = ui
    select(st, PANELS[1])
    crm.show_crm_page()
    clients.assert_called_once()
    pipe.assert_not_called()
    inbox.assert_not_called()
    requests.assert_not_called()
    st.tabs.assert_not_called()


def test_history_does_not_read_pipeline_or_clients(ui):
    st, _, pipe, clients, inbox, requests = ui
    select(st, PANELS[2])
    crm.show_crm_page()
    pipe.assert_not_called()
    clients.assert_not_called()
    inbox.assert_not_called()
    requests.assert_not_called()
    st.button.assert_called_once()
    assert st.button.call_args.args[0] == "Afficher l'historique CRM"


def test_site_inbox_requires_flag_and_loads_no_other_panel(ui):
    st, _, pipe, clients, inbox, requests = ui
    select(st, PANELS[3])
    inbox.return_value = True
    crm.show_crm_page()
    inbox.assert_called_once()
    requests.assert_called_once()
    pipe.assert_not_called()
    clients.assert_not_called()
    st.tabs.assert_not_called()


def test_unlogged_session_denied_before_navigation(ui):
    st, perm, pipe, clients, inbox, requests = ui
    st.session_state["authenticated"] = False
    crm.show_crm_page()
    st.selectbox.assert_not_called()
    perm.assert_not_called()
    pipe.assert_not_called()
    clients.assert_not_called()
    inbox.assert_not_called()
    requests.assert_not_called()
    st.error.assert_called_once()


def test_no_read_role_denied_before_business_calls(ui):
    st, perm, pipe, clients, inbox, requests = ui
    perm.side_effect = lambda _r, _m, action: action != "lecture"
    crm.show_crm_page()
    st.selectbox.assert_not_called()
    perm.assert_called_once_with("ADMIN", "CRM", "lecture")
    pipe.assert_not_called()
    clients.assert_not_called()
    inbox.assert_not_called()
    requests.assert_not_called()


def test_read_only_interaction_view_skips_clients_and_write_form(ui):
    st, perm, pipe, clients, inbox, requests = ui
    select(st, PANELS[1])
    perm.side_effect = lambda _r, _m, action: action == "lecture"
    crm.show_crm_page()
    clients.assert_not_called()
    st.form.assert_not_called()
    pipe.assert_not_called()
    requests.assert_not_called()


def test_navigation_activity_and_all_four_panels_remain_available(ui):
    st, _, _, _, _, _ = ui
    select(st, PANELS[3])
    crm.show_crm_page()
    call = next(x for x in st.selectbox.call_args_list
                if x.args and x.args[0] == "Vue CRM")
    assert tuple(call.args[1]) == PANELS
    assert call.kwargs["on_change"] is crm._mark_crm_activity
    crm._mark_crm_activity()
    assert st.session_state["_erp_crm_interacted"] is True
    assert "last_activity" not in st.session_state
