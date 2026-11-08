"""SEC-ADMIN : le rôle Administration vient du compte serveur, pas de session.

Tous les cas sont hors réseau. Le compte en PROD n'est jamais manipulé.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, call

import pytest
from modules.admin import views as admin


def _user(role="ADMIN", actif="OUI", user_id="USR-ADMIN"):
    return {"user_id": user_id, "role": role, "actif": actif}


@pytest.fixture
def ui(monkeypatch):
    st = MagicMock()
    st.session_state = {
        "authenticated": True,
        "user": {"user_id": "USR-ADMIN", "role": "ADMIN"},
    }
    monkeypatch.setattr(admin, "st", st)
    permissions = MagicMock(return_value=True)
    monkeypatch.setattr(admin, "has_permission", permissions)
    client = MagicMock()
    query = (client.table.return_value.select.return_value
             .eq.return_value.limit.return_value)
    query.execute.return_value = SimpleNamespace(data=[_user()])
    monkeypatch.setattr(admin, "get_supabase_client",
                        MagicMock(return_value=client))
    return st, permissions, client, query


def test_active_admin_uses_fresh_server_role(ui):
    st, perms, client, query = ui
    assert admin._admin_access() is True
    client.table.assert_called_once_with("users")
    client.table.return_value.select.assert_called_once_with("user_id,role,actif")
    client.table.return_value.select.return_value.eq.assert_called_once_with(
        "user_id", "USR-ADMIN"
    )
    client.table.return_value.select.return_value.eq.return_value.limit.assert_called_once_with(2)
    assert perms.call_args_list == [
        call("ADMIN", "Administration", "lecture"),
        call("ADMIN", "Administration", "ecriture"),
    ]


@pytest.mark.parametrize("invalid", [
    [], [_user(), _user()], [_user(user_id="OTHER")],
    [_user(actif="NON")], [_user(actif=False)],
    [_user(actif=None)], [_user(actif=1)],
    [_user(role="")], [_user(role=None)],
    [{"user_id": "USR-ADMIN", "role": "ADMIN"}],
    [None], {"wrong": "shape"},
])
def test_invalid_backend_account_never_authorizes_admin(ui, invalid):
    st, perms, client, query = ui
    query.execute.return_value = SimpleNamespace(data=invalid)
    assert admin._admin_access() is None
    perms.assert_not_called()


@pytest.mark.parametrize("authenticated,user", [
    (False, {"user_id": "USR-ADMIN", "role": "ADMIN"}),
    ("yes", {"user_id": "USR-ADMIN", "role": "ADMIN"}),
    (True, None), (True, {}), (True, {"role": "ADMIN"}),
    (True, {"user_id": "", "role": "ADMIN"}),
    (True, {"user_id": 123, "role": "ADMIN"}),
])
def test_invalid_session_does_not_contact_backend(ui, authenticated, user):
    st, perms, client, query = ui
    st.session_state["authenticated"] = authenticated
    st.session_state["user"] = user
    assert admin._admin_access() is None
    admin.get_supabase_client.assert_not_called()
    perms.assert_not_called()


def test_stale_admin_role_in_session_is_not_used(ui):
    st, perms, client, query = ui
    query.execute.return_value = SimpleNamespace(data=[_user(role="LECTEUR")])
    perms.side_effect = lambda role, module, op: (
        role == "LECTEUR" and module == "Administration" and op == "lecture"
    )
    assert admin._admin_access() is False
    assert perms.call_args_list == [
        call("LECTEUR", "Administration", "lecture"),
        call("LECTEUR", "Administration", "ecriture"),
    ]


def test_server_revokes_read_right_even_if_session_still_admin(ui):
    st, perms, client, query = ui
    query.execute.return_value = SimpleNamespace(data=[_user(role="REVOQUE")])
    perms.return_value = False
    assert admin._admin_access() is None
    perms.assert_called_once_with("REVOQUE", "Administration", "lecture")


def test_network_error_is_refused_without_exposing_details(ui):
    st, perms, client, query = ui
    admin.get_supabase_client.side_effect = RuntimeError("SECRET-CONNEXION")
    assert admin._admin_access() is None
    perms.assert_not_called()
    admin.show_admin_page()
    st.selectbox.assert_not_called()
    st.error.assert_called_once_with(
        "Accès Administration refusé : compte ou droits non vérifiables."
    )
    assert "SECRET-CONNEXION" not in str(st.error.call_args)


def test_revocation_between_two_renders_prevents_second_view(ui, monkeypatch):
    st, perms, client, query = ui
    query.execute.side_effect = [
        SimpleNamespace(data=[_user()]),
        SimpleNamespace(data=[_user(actif="NON")]),
    ]
    # Aucun accès au véritable référentiel : premier rendu sur Listes de choix
    st.selectbox.side_effect = (
        lambda label, opts, **kw: "📝 Listes de choix"
        if label == "Vue Administration" else list(opts)[0]
    )
    st.checkbox.return_value = False
    monkeypatch.setattr(admin, "get_opts", MagicMock())
    admin.show_admin_page()
    assert st.selectbox.call_count == 1
    admin.show_admin_page()
    assert st.selectbox.call_count == 1
    assert query.execute.call_count == 2
    st.error.assert_called_once_with(
        "Accès Administration refusé : compte ou droits non vérifiables."
    )


def test_sanitized_denial_before_any_catalogue_reads(ui, monkeypatch):
    st, perms, client, query = ui
    query.execute.return_value = SimpleNamespace(data=[_user(actif="NON")])
    catalog = MagicMock()
    monkeypatch.setattr(admin, "get_opts", catalog)
    admin.show_admin_page()
    st.selectbox.assert_not_called()
    catalog.assert_not_called()
    st.error.assert_called_once()
