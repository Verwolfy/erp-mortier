"""Tests isolés du futur onglet CRM NextGen : aucune connexion externe."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import sys
import types
from unittest.mock import Mock

import pytest

FILE = Path(__file__).parents[1] / "modules" / "crm" / "site_requests.py"
VIEWS = Path(__file__).parents[1] / "modules" / "crm" / "views.py"
UID = "00000000-0000-4000-8000-000000000001"


@pytest.fixture
def env(monkeypatch):
    st = types.ModuleType("streamlit")
    st.secrets = {"nextgen": {"crm_inbox_read_enabled": True, "privacy_review_approved": True}}
    st.session_state = {"authenticated": True, "user": {"user_id": "U1", "role": "ADMIN"}}
    roles = types.ModuleType("config.roles")
    roles.has_permission = Mock(return_value=True)
    db_module = types.ModuleType("core.db_service")
    client = Mock()
    users = Mock()
    requests = Mock()
    users.select.return_value = users
    users.eq.return_value = users
    users.limit.return_value = users
    users.execute.return_value = types.SimpleNamespace(
        data=[{"user_id": "U1", "role": "COMMERCIAL", "actif": "OUI"}]
    )
    requests.select.return_value = requests
    requests.order.return_value = requests
    requests.limit.return_value = requests
    requests.execute.return_value = types.SimpleNamespace(data=[])
    client.table.side_effect = lambda table: {
        "users": users, "site_demandes": requests
    }[table]
    db_module.get_supabase_client = Mock(return_value=client)
    for name, module in {"streamlit": st, "config.roles": roles, "core.db_service": db_module}.items():
        monkeypatch.setitem(sys.modules, name, module)
    spec = importlib.util.spec_from_file_location("nextgen_crm_inbox_test", FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return types.SimpleNamespace(m=module, st=st, roles=roles, db=db_module,
                                 client=client, users=users, requests=requests)


def row(**updates):
    out = {"demande_id": UID, "type_demande": "quote",
           "statut": "nouveau", "cree_le": "2026-11-01T09:00:00+00:00"}
    return dict(out, **updates)


@pytest.mark.parametrize("cfg", [
    None, {}, {"crm_inbox_read_enabled": False},
    {"crm_inbox_read_enabled": "true"}, {"crm_inbox_read_enabled": 1}
])
def test_flag_fails_closed(env, cfg):
    env.st.secrets = {"nextgen": cfg} if cfg is not None else {}
    assert env.m.inbox_enabled() is False
    with pytest.raises(PermissionError):
        env.m.list_requests_readonly()
    env.db.get_supabase_client.assert_not_called()


def test_unlogged_does_not_contact_database(env):
    env.st.session_state["authenticated"] = "yes"
    with pytest.raises(PermissionError):
        env.m.list_requests_readonly()
    env.db.get_supabase_client.assert_not_called()


@pytest.mark.parametrize("session", [None, {}, {"user_id": 3}, {"role": "ADMIN"}])
def test_identity_missing_blocks_requests(env, session):
    env.st.session_state["user"] = session
    with pytest.raises(PermissionError):
        env.m.list_requests_readonly()
    env.requests.select.assert_not_called()


@pytest.mark.parametrize("account", [
    [], [{}, {}], [{"user_id": "U2", "role": "ADMIN", "actif": "OUI"}],
    [{"user_id": "U1", "role": "ADMIN", "actif": "NON"}],
    [{"user_id": "U1", "role": None, "actif": "OUI"}],
])
def test_invalid_db_identity_blocks(env, account):
    env.users.execute.return_value.data = account
    with pytest.raises(PermissionError):
        env.m.list_requests_readonly()
    env.requests.select.assert_not_called()


def test_fresh_role_and_permissions_not_session(env):
    env.requests.execute.return_value.data = [row()]
    records, has_more = env.m.list_requests_readonly()
    assert records == [row()] and has_more is False
    env.roles.has_permission.assert_called_once_with("COMMERCIAL", "CRM", "lecture")
    env.users.select.assert_called_once_with("user_id,role,actif")
    env.requests.select.assert_called_once_with("demande_id,type_demande,statut,cree_le")
    env.requests.order.assert_called_once_with("cree_le", desc=True)
    env.requests.limit.assert_called_once_with(101)
    assert "insert" not in str(env.requests.method_calls)
    assert "update" not in str(env.requests.method_calls)


def test_denied_permission_blocks_requests(env):
    env.roles.has_permission.return_value = False
    with pytest.raises(PermissionError):
        env.m.list_requests_readonly()
    env.requests.select.assert_not_called()


@pytest.mark.parametrize("bad", [
    {"email": "nope"}, {"telephone": "nope"}, {"message": "secret"},
    {"statut": "invalide"}, {"demande_id": "not-a-uuid"},
    {"type_demande": "unknown"}, {"cree_le": None},
])
def test_unexpected_record_rejected(env, bad):
    env.requests.execute.return_value.data = [row(**bad)]
    with pytest.raises(ValueError):
        env.m.list_requests_readonly()


def test_bounded_recent_requests(env):
    env.requests.execute.return_value.data = [row() for _ in range(101)]
    records, more = env.m.list_requests_readonly()
    assert len(records) == 100 and more is True


def test_non_list_response_refused(env):
    env.requests.execute.return_value.data = {"data": []}
    with pytest.raises(ValueError):
        env.m.list_requests_readonly()


def test_ui_is_read_only_and_tab_present():
    source = VIEWS.read_text(encoding="utf-8")
    assert '🌐 Demandes NextGen' in source
    assert "list_requests_readonly()" in source
    assert "if not inbox_enabled():" in source
    # New tab never collects contacts or invokes legacy write helpers.
    segment = source.split("if active_panel == panels[3]:", 1)[1]
    assert "create_opportunite(" not in segment
    assert "create_interaction(" not in segment
    assert ".insert(" not in segment and ".update(" not in segment
    assert "form_submit_button(" not in segment


@pytest.mark.parametrize("approval", [None, False, "true", 1])
def test_privacy_review_approval_is_distinct_required_gate(env, approval):
    env.st.secrets = {"nextgen": {"crm_inbox_read_enabled": True}}
    if approval is not None:
        env.st.secrets["nextgen"]["privacy_review_approved"] = approval
    assert env.m.inbox_enabled() is False
    with pytest.raises(PermissionError):
        env.m.list_requests_readonly()
    env.db.get_supabase_client.assert_not_called()


def test_mapping_compatible_with_streamlit_secret_wrappers(env):
    from types import MappingProxyType
    env.st.secrets = {"nextgen": MappingProxyType({
        "crm_inbox_read_enabled": True, "privacy_review_approved": True
    })}
    assert env.m.inbox_enabled() is True


def test_nextgen_inbox_has_version_fingerprint_for_operator_readonly_checks():
    source = VIEWS.read_text(encoding="utf-8")
    segment = source.split("if active_panel == panels[3]:", 1)[1]
    assert "SOF-NEXTGEN-CRM-20261101-L9" in segment
    assert "st.caption(" in segment
    assert "if not inbox_enabled():" in segment
