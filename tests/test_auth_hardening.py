"""Tests isolés : aucun appel au réseau ni aux véritables données Supabase."""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import types

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class Query:
    def __init__(self, data, error=None):
        self.data = list(data)
        self.error = error
        self.conditions = []
        self.limit_n = None
        self.selections = []

    def select(self, columns):
        self.selections.append(columns)
        return self

    def eq(self, field, value):
        self.conditions.append(("eq", field, value))
        return self

    def ilike(self, field, value):
        self.conditions.append(("ilike", field, value))
        return self

    def limit(self, size):
        self.limit_n = size
        return self

    def execute(self):
        if self.error:
            raise self.error
        result = self.data
        for kind, column, expected in self.conditions:
            if kind == "eq":
                result = [r for r in result if r.get(column) == expected]
            else:
                result = [r for r in result if
                          str(r.get(column, "")).casefold() == str(expected).casefold()]
        if self.limit_n is not None:
            result = result[:self.limit_n]
        return types.SimpleNamespace(data=result)


class Client:
    def __init__(self, tables, errors=None):
        self.tables = tables
        self.errors = errors or {}
        self.calls = []

    def table(self, name):
        self.calls.append(name)
        return Query(self.tables.get(name, []), error=self.errors.get(name))


class DummyStreamlit(types.ModuleType):
    def __init__(self):
        super().__init__("streamlit")
        self.session_state = {}
        self.logs = []
        self.responses = ("", "", False)

        def cache_data(*args, **kwargs):
            return lambda func: func
        self.cache_data = cache_data
        self.cache_data.clear = lambda: self.logs.append(("cache_clear",))

    def __getattr__(self, item):
        if item in {"title", "markdown", "warning", "error", "success"}:
            return lambda *a, **kw: self.logs.append((item, *a))
        raise AttributeError(item)

    def form(self, name):
        class Ctx:
            def __enter__(self):
                return None
            def __exit__(self, *args):
                return False
        return Ctx()

    def text_input(self, label, **kwargs):
        return self.responses[0] if "Identifiant" in label else self.responses[1]

    def form_submit_button(self, *args, **kwargs):
        return self.responses[2]

    def rerun(self):
        self.logs.append(("rerun",))


class DummyBcrypt(types.ModuleType):
    """Uniquement pour tests de flux : ne représente PAS une implémentation cryptographique."""
    def __init__(self):
        super().__init__("bcrypt")
        self.count = 0

    def gensalt(self, rounds=12):
        return b"salt"

    def hashpw(self, password, salt):
        return b"$2b$" + salt + b":" + password

    def checkpw(self, password, stored):
        self.count += 1
        if not isinstance(stored, bytes) or not stored.startswith(b"$2b$"):
            raise ValueError("bad hash")
        return stored.rsplit(b":", 1)[-1] == password


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def ctx(monkeypatch):
    st = DummyStreamlit()
    bcrypt = DummyBcrypt()
    client = Client({"users": [], "permissions": []})
    db = types.ModuleType("core.db_service")
    db.get_supabase_client = lambda: client
    monkeypatch.setitem(sys.modules, "streamlit", st)
    monkeypatch.setitem(sys.modules, "bcrypt", bcrypt)
    monkeypatch.setitem(sys.modules, "core.db_service", db)
    roles = load("config/roles.py", "_test_roles")
    service = load("modules/auth/service.py", "_test_service")
    monkeypatch.setitem(sys.modules, "modules.auth.service", service)
    views = load("modules/auth/views.py", "_test_views")
    yield types.SimpleNamespace(st=st, bcrypt=bcrypt, client=client,
                                roles=roles, service=service, views=views)
    for name in ("_test_roles", "_test_service", "_test_views"):
        sys.modules.pop(name, None)


def account(ctx, login="bob", passwd="pass123", **changes):
    row = dict(user_id="u-01", nom="Bob", login=login, hash_mdp=ctx.service.hash_password(passwd),
               role="Magasinier", actif="OUI")
    row.update(changes)
    ctx.client.tables["users"] = [row]
    return row


def right(**overrides):
    item = dict(role="Magasinier", module="Stocks", lecture="OUI", ecriture="NON")
    item.update(overrides)
    return item


def test_auth_correct(ctx):
    account(ctx)
    assert ctx.service.authenticate_user("bob", "pass123") == {
        "user_id": "u-01", "nom": "Bob", "role": "Magasinier"
    }


@pytest.mark.parametrize("password", ["wrong", "", "x" * 73])
def test_auth_wrong_password(ctx, password):
    account(ctx)
    assert ctx.service.authenticate_user("bob", password) is None


@pytest.mark.parametrize("login", ["missing", "", "a" * 129])
def test_auth_invalid_login(ctx, login):
    account(ctx)
    assert ctx.service.authenticate_user(login, "pass123") is None


def test_missing_user_does_dummy_bcrypt(ctx):
    assert ctx.service.authenticate_user("missing", "a") is None
    assert ctx.bcrypt.count == 1


@pytest.mark.parametrize("active", ["NON", None, False, "0"])
def test_inactive_user(ctx, active):
    account(ctx, actif=active)
    assert ctx.service.authenticate_user("bob", "pass123") is None


def test_boolean_active(ctx):
    account(ctx, actif=True)
    assert ctx.service.authenticate_user("bob", "pass123") is not None


def test_missing_role(ctx):
    account(ctx, role="")
    assert ctx.service.authenticate_user("bob", "pass123") is None


def test_missing_user_id(ctx):
    account(ctx, user_id="")
    assert ctx.service.authenticate_user("bob", "pass123") is None


def test_duplicate_accounts_fail_closed(ctx):
    a = account(ctx)
    ctx.client.tables["users"] = [a.copy(), a.copy()]
    assert ctx.service.authenticate_user("bob", "pass123") is None


def test_broken_hash_fails_closed(ctx):
    account(ctx, hash_mdp="not-bcrypt")
    assert ctx.service.authenticate_user("bob", "pass123") is None


def test_db_outage_distinct_from_bad_password(ctx):
    ctx.client.errors["users"] = ConnectionError("sensitive token")
    with pytest.raises(ctx.service.AuthenticationBackendError, match="indisponible"):
        ctx.service.authenticate_user("bob", "pass123")


def test_hash_password(ctx):
    assert ctx.service.hash_password("secret").startswith("$2b$")


@pytest.mark.parametrize("pw", ["", "é" * 40, None])
def test_hash_rejects_invalid(ctx, pw):
    with pytest.raises(ValueError):
        ctx.service.hash_password(pw)


def test_permissions_can_read(ctx):
    ctx.client.tables["permissions"] = [right()]
    assert ctx.roles.has_permission("magasinier", "STOCKS", "lecture") is True


def test_permissions_cannot_write(ctx):
    ctx.client.tables["permissions"] = [right()]
    assert ctx.roles.has_permission("Magasinier", "Stocks", "ecriture") is False


def test_permission_write_allowed(ctx):
    ctx.client.tables["permissions"] = [right(ecriture="OUI")]
    assert ctx.roles.has_permission("Magasinier", "Stocks", "ecriture") is True


@pytest.mark.parametrize("value", ["non", "", "FALSE", None, "maybe"])
def test_permission_invalid_values(ctx, value):
    ctx.client.tables["permissions"] = [right(ecriture=value)]
    assert ctx.roles.has_permission("Magasinier", "Stocks", "ecriture") is False


def test_permission_duplicate_denied(ctx):
    ctx.client.tables["permissions"] = [right(ecriture="OUI"), right(ecriture="NON")]
    assert ctx.roles.has_permission("Magasinier", "Stocks", "ecriture") is False


def test_admin_rights_still_supported(ctx):
    assert ctx.roles.has_permission("ADMIN", "Stocks", "ecriture") is True
    assert "Finance" in ctx.roles.get_allowed_modules("ADMIN")


def test_admin_invalid_perm_denied(ctx):
    assert ctx.roles.has_permission("ADMIN", "Stocks", "delete") is False


def test_permissions_no_client_access(ctx):
    ctx.client.errors["permissions"] = RuntimeError("token private")
    assert ctx.roles.has_permission("Magasinier", "Stocks", "lecture") is False


def test_menu_reads_supabase_not_sheets(ctx):
    ctx.client.tables["permissions"] = [right()]
    assert ctx.roles.get_allowed_modules("Magasinier") == ["Stocks"]
    assert ctx.client.calls == ["permissions"]


def test_menu_duplicate_denied(ctx):
    ctx.client.tables["permissions"] = [right(), right()]
    assert ctx.roles.get_allowed_modules("Magasinier") == []


def test_malformed_permissions_denied(ctx):
    ctx.client.tables["permissions"] = ["broken-row"]
    assert ctx.roles.has_permission("Magasinier", "Stocks", "lecture") is False


def test_permissions_limit_denied(ctx):
    ctx.client.tables["permissions"] = [right()] * 1000
    assert ctx.roles.has_permission("Magasinier", "Stocks", "lecture") is False


def test_invalid_roles_denied(ctx):
    assert ctx.roles.has_permission("", "Stocks", "lecture") is False
    assert ctx.roles.has_permission("Magasinier", "", "lecture") is False
    assert ctx.roles.has_permission(None, "Stocks", "lecture") is False
    assert ctx.roles.get_allowed_modules("") == []


def test_login_form_success(ctx):
    account(ctx)
    ctx.st.responses = ("bob", "pass123", True)
    ctx.views.show_login_page()
    assert ctx.st.session_state["authenticated"] is True
    assert ctx.st.session_state["user"]["user_id"] == "u-01"
    assert any(x[0] == "rerun" for x in ctx.st.logs)


def test_login_failure_counts(ctx):
    ctx.st.responses = ("nobody", "wrong", True)
    ctx.views.show_login_page()
    assert ctx.st.session_state["login_attempts"] == 1


def test_lockout_after_three_failures(ctx):
    ctx.st.responses = ("nobody", "wrong", True)
    for _ in range(3):
        ctx.views.show_login_page()
    assert ctx.st.session_state["login_attempts"] == 3
    assert ctx.st.session_state["lockout_time"] > 0


def test_service_outage_not_counted_as_wrong_password(ctx):
    ctx.st.responses = ("bob", "pass123", True)
    ctx.client.errors["users"] = OSError("unavailable")
    ctx.views.show_login_page()
    assert ctx.st.session_state["login_attempts"] == 0
    assert any(x[0] == "error" and "temporairement" in x[1] for x in ctx.st.logs)


def test_form_not_submitted(ctx):
    ctx.st.responses = ("bob", "pass123", False)
    ctx.views.show_login_page()
    assert ctx.client.calls == []


def test_blank_login_warning(ctx):
    ctx.st.responses = ("", "pass123", True)
    ctx.views.show_login_page()
    assert ctx.client.calls == []
    assert any(x[0] == "warning" for x in ctx.st.logs)


def test_logout_keeps_historical_cache_purge(ctx):
    ctx.st.session_state.update(authenticated=True, user={"user_id": "u-01"})
    ctx.views.logout()
    assert ctx.st.session_state["authenticated"] is False
    assert ctx.st.session_state["user"] is None
    assert ("rerun",) in ctx.st.logs
    assert ("cache_clear",) in ctx.st.logs


def test_permissions_query_does_not_fetch_password_hashes(ctx):
    ctx.client.tables["permissions"] = [right()]
    ctx.roles.has_permission("Magasinier", "Stocks", "lecture")
    assert "users" not in ctx.client.calls


def test_login_selects_one_account_only(ctx):
    account(ctx)
    ctx.service.authenticate_user("bob", "pass123")
    assert ctx.client.calls == ["users"]


def test_active_lockout_disables_form(ctx):
    import time
    ctx.st.session_state["lockout_time"] = time.time() + 45
    ctx.st.responses = ("bob", "pass123", True)
    ctx.views.show_login_page()
    assert ctx.client.calls == []


def test_expired_lockout_resets_counter(ctx):
    ctx.st.session_state["lockout_time"] = 1
    ctx.st.session_state["login_attempts"] = 3
    ctx.st.responses = ("bob", "incorrect", True)
    ctx.views.show_login_page()
    assert ctx.st.session_state["login_attempts"] == 1


def test_corrupt_bcrypt_hash_denied(ctx, monkeypatch):
    account(ctx)
    def invalid_hash(password, hash_value):
        raise ValueError("corrupt")
    monkeypatch.setattr(ctx.bcrypt, "checkpw", invalid_hash)
    assert ctx.service.authenticate_user("bob", "pass123") is None


def test_login_does_not_reveal_password_hash(ctx):
    account(ctx)
    result = ctx.service.authenticate_user("bob", "pass123")
    assert "hash_mdp" not in result and "login" not in result


def test_accounts_cannot_be_taken_from_sheets(ctx):
    account(ctx)
    ctx.service.authenticate_user("bob", "pass123")
    assert ctx.client.calls == ["users"]


def test_permission_multi_role_separation(ctx):
    ctx.client.tables["permissions"] = [right(role="Commercial", ecriture="OUI")]
    assert ctx.roles.has_permission("Magasinier", "Stocks", "ecriture") is False


def test_permissions_subtle_invalid_type(ctx):
    assert ctx.roles.has_permission("ADMIN", "Stocks", "ECRITURE") is False


def test_roles_with_whitespace_are_normalized(ctx):
    ctx.client.tables["permissions"] = [right(ecriture="OUI")]
    assert ctx.roles.has_permission(" Magasinier ", " stocks ", "ecriture") is True
