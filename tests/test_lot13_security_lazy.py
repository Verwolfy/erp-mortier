"""Lot 13 : les 4 vues Sécurité ne lisent que la source sélectionnée."""
from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest
from modules.admin import views as admin


PANELS = (
    "Créer un Utilisateur", "Définir les Permissions",
    "Annuaire Existant", "Piste d'Audit (Logs)",
)


@pytest.fixture
def ui(monkeypatch):
    st = MagicMock()
    st.session_state = {"user": {"user_id": "USR-SEC-TEST", "role": "ADMIN"}}
    st.columns.return_value = [MagicMock(), MagicMock()]
    st.form_submit_button.return_value = False
    st.button.return_value = False
    st.selectbox.side_effect = (
        lambda _label, options, **_kw: list(options)[0]
    )
    monkeypatch.setattr(admin, "st", st)
    gate = MagicMock(return_value=True)
    monkeypatch.setattr(admin, "is_security_manager", gate)
    users = MagicMock(return_value=pd.DataFrame([{
        "user_id": "USR-1", "nom": "Test", "hash_mdp": "NE-PAS-AFFICHER",
    }]))
    perms = MagicMock(return_value=pd.DataFrame([{
        "role": "TEST", "module": "CRM", "lecture": "OUI",
    }]))
    logs = MagicMock(return_value=pd.DataFrame([{"action": "AUDIT"}]))
    monkeypatch.setattr(admin, "get_users", users)
    monkeypatch.setattr(admin, "get_permissions", perms)
    monkeypatch.setattr(admin, "get_audit_logs", logs)
    return st, gate, users, perms, logs


@pytest.mark.parametrize("panel,index", [
    ("Créer un Utilisateur", 0),
    ("Définir les Permissions", 1),
    ("Annuaire Existant", 2),
    ("Piste d'Audit (Logs)", 3),
])
def test_each_security_panel_is_exclusive(ui, panel, index):
    st, gate, users, perms, logs = ui
    st.selectbox.side_effect = (
        lambda label, options, **kw:
        panel if label == "Vue Sécurité" else list(options)[0]
    )
    admin.show_user_management()
    gate.assert_called_once()
    assert users.call_count == (1 if index == 2 else 0)
    assert perms.call_count == (1 if index == 2 else 0)
    assert logs.call_count == (1 if index == 3 else 0)
    assert st.form.call_count == (1 if index in (0, 1) else 0)
    st.tabs.assert_not_called()


def test_audit_logs_never_fetched_while_creating_user(ui):
    st, _, users, perms, logs = ui
    admin.show_user_management()
    users.assert_not_called()
    perms.assert_not_called()
    logs.assert_not_called()
    st.form.assert_called_once_with("form_add_user", clear_on_submit=True)


def test_security_manager_gate_denies_before_selector_and_reads(ui):
    st, gate, users, perms, logs = ui
    gate.return_value = False
    admin.show_user_management()
    st.selectbox.assert_not_called()
    st.form.assert_not_called()
    users.assert_not_called()
    perms.assert_not_called()
    logs.assert_not_called()
    st.error.assert_called_once_with("Habilitation SECURITY_MANAGER requise.")


def test_password_hash_is_not_rendered_in_directory(ui):
    st, _, users, perms, logs = ui
    st.selectbox.side_effect = (
        lambda label, options, **kw:
        "Annuaire Existant" if label == "Vue Sécurité" else list(options)[0]
    )
    admin.show_user_management()
    assert users.call_count == 1
    assert st.dataframe.call_count == 2
    shown_user_frame = st.dataframe.call_args_list[0].args[0]
    assert "hash_mdp" not in shown_user_frame.columns
    assert "user_id" in shown_user_frame.columns


def test_navigation_activity_without_session_refresh(ui):
    st, _, _, _, _ = ui
    admin.show_user_management()
    choice = next(c for c in st.selectbox.call_args_list
                  if c.args and c.args[0] == "Vue Sécurité")
    assert tuple(choice.args[1]) == PANELS
    assert choice.kwargs["on_change"] is admin._mark_admin_activity
    admin._mark_admin_activity()
    assert st.session_state["_erp_admin_interacted"] is True
    assert "last_activity" not in st.session_state
