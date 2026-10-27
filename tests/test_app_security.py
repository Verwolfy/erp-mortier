"""Tests hors-ligne du point d'entrée ; aucune écriture Supabase."""
from __future__ import annotations

import importlib.util
import math
import pathlib
import sys
import types
from unittest.mock import Mock

import pytest

APP_PATH = pathlib.Path(__file__).resolve().parents[1] / "app.py"
MODULES = ("streamlit", "config", "config.roles", "core", "core.db_service",
           "modules", "modules.auth", "modules.auth.views")


class Sidebar:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class Session(dict):
    pass


@pytest.fixture
def env(monkeypatch):
    st = types.ModuleType("streamlit")
    st.session_state = Session()
    st.sidebar = Sidebar()
    st.set_page_config = Mock()
    st.warning = Mock()
    st.error = Mock()
    st.write = Mock()
    st.caption = Mock()
    st.button = Mock(return_value=False)
    st.divider = Mock()
    st.subheader = Mock()
    st.radio = Mock(side_effect=lambda label, options, format_func, **kwargs: options[0])

    roles = types.ModuleType("config.roles")
    roles.get_allowed_modules = Mock(return_value=["Administration", "Stocks", "RH"])
    roles.has_permission = Mock(return_value=True)
    auth = types.ModuleType("modules.auth.views")
    auth.logout = Mock()
    auth.show_login_page = Mock()

    client = Mock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"user_id": "u1", "role": "Admin", "nom": "Test", "actif": "OUI"}
    ]
    db = types.ModuleType("core.db_service")
    db.get_supabase_client = Mock(return_value=client)
    security = types.ModuleType("core.security_service")
    security.is_security_manager = Mock(return_value=False)

    config = types.ModuleType("config")
    config.__path__ = []
    config.roles = roles
    core = types.ModuleType("core")
    core.__path__ = []
    core.db_service = db
    core.security_service = security
    modules = types.ModuleType("modules")
    modules.__path__ = []
    modules_auth = types.ModuleType("modules.auth")
    modules_auth.__path__ = []
    modules_auth.views = auth

    for key, mod in {
        "streamlit": st, "config": config, "config.roles": roles,
        "core": core, "core.db_service": db, "core.security_service": security,
        "modules": modules, "modules.auth": modules_auth,
        "modules.auth.views": auth,
    }.items():
        monkeypatch.setitem(sys.modules, key, mod)

    spec = importlib.util.spec_from_file_location("app", APP_PATH)
    app = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "app", app)
    spec.loader.exec_module(app)
    assert st.set_page_config.call_count == 1

    st.session_state.update({
        "authenticated": True,
        "user": {"user_id": "u1", "role": "AncienRole", "nom": "Old"},
        "last_activity": 999,
    })
    monkeypatch.setattr(app.time, "time", lambda: 1000)
    return types.SimpleNamespace(st=st, app=app, client=client, db=db, auth=auth, roles=roles, security=security)


def test_fresh_role_from_db(env):
    user = env.app._verified_user(1000)
    assert user["role"] == "Admin"
    assert env.st.session_state["user"]["role"] == "Admin"
    assert env.st.session_state["last_activity"] == 999
    env.client.table.assert_called_once_with("users")
    q = env.client.table.return_value.select.return_value
    q.eq.assert_called_once_with("user_id", "u1")
    env.client.table.return_value.select.assert_called_once_with("user_id,nom,role,actif")


@pytest.mark.parametrize("stamp", [None, "1000", True, False, float("nan"), float("inf"),
                                   float("-inf"), 1000.0001, -800, -900, -2000])
def test_expired_rejects_bad_time(env, stamp):
    assert env.app._session_expired(stamp, 1000) is True


@pytest.mark.parametrize("stamp", [1000, 999, 500])
def test_time_valid(env, stamp):
    assert env.app._session_expired(stamp, 1000) is False


@pytest.mark.parametrize("active", [True, 1, "OUI", "true", "  ACTIF ", "Yes", "1"])
def test_active_values(env, active):
    assert env.app._active(active)


@pytest.mark.parametrize("active", [False, None, 0, "", "NON", "inactive", [], "NO"])
def test_inactive_values(env, active):
    assert not env.app._active(active)


@pytest.mark.parametrize("user", [None, {}, "admin", {"user_id": ""}, {"user_id": 1}])
def test_invalid_user_is_logged_out(env, user):
    env.st.session_state["user"] = user
    assert env.app._verified_user(1000) is None
    env.auth.logout.assert_called_once()
    env.db.get_supabase_client.assert_not_called()


def test_expired_logout(env):
    env.st.session_state["last_activity"] = 100
    assert env.app._verified_user(2001) is None
    env.auth.logout.assert_called_once()
    env.st.warning.assert_called_once()


@pytest.mark.parametrize("rows", [[], [None], [{}], ["bad"],
                                  [{"user_id": "u2", "role": "ADMIN", "actif": "OUI"}],
                                  [{"user_id": "u1", "role": "ADMIN", "actif": "NON"}],
                                  [{"user_id": "u1", "role": "", "actif": "OUI"}],
                                  [{"user_id": "u1", "role": None, "actif": "OUI"}],
                                  [{"user_id": "u1", "role": "ADMIN", "actif": "OUI"}] * 2,
                                  None, "bad"])
def test_invalid_or_inactive_db_account(env, rows):
    env.client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = rows
    assert env.app._verified_user(1000) is None
    env.auth.logout.assert_called_once()


def test_backend_unavailable_blocks_without_logout(env):
    env.db.get_supabase_client.side_effect = TimeoutError("secret")
    assert env.app._verified_user(1000) is None
    env.st.error.assert_called_once()
    assert "secret" not in str(env.st.error.call_args)
    env.auth.logout.assert_not_called()
    assert env.st.session_state["last_activity"] == 999


def test_main_for_unauthenticated(env):
    env.st.session_state["authenticated"] = False
    env.app.main()
    env.auth.show_login_page.assert_called_once()
    env.db.get_supabase_client.assert_not_called()


def test_main_incomplete_session_blocks_menu(env):
    env.st.session_state["user"] = None
    env.app.main()
    env.auth.logout.assert_called_once()
    env.st.radio.assert_not_called()


def test_main_invalid_boolean_auth(env):
    env.st.session_state["authenticated"] = "yes"
    env.app.main()
    env.auth.show_login_page.assert_called_once()
    env.db.get_supabase_client.assert_not_called()


def test_menu_read_only_admin_no_security(env):
    env.roles.get_allowed_modules.return_value = ["administration", "Stocks"]
    env.roles.has_permission.return_value = False
    menu = env.app._allowed_menu("reader")
    assert "Administration" in menu
    assert "Securite" not in menu
    assert "Stocks" in menu
    assert "Help" in menu


def test_menu_with_security_and_deduped(env):
    env.roles.get_allowed_modules.return_value = ["  Administration ", "Stocks", "stocks", "UNKNOWN", "  rH  "]
    # Le role ADMIN seul n'accorde jamais l'habilitation nominative.
    assert list(env.app._allowed_menu("Admin")) == ["Administration", "Stocks", "RH", "Help"]
    env.security.is_security_manager.return_value = True
    assert list(env.app._allowed_menu("Admin")) == ["Administration", "Stocks", "RH", "Securite", "Help"]


def test_help_menu_for_no_business_permissions(env):
    env.roles.get_allowed_modules.return_value = []
    env.roles.has_permission.return_value = False
    assert env.app._allowed_menu("reader") == {"Help": "📚 Guide & Aide"}


def test_main_backend_error_no_navigation(env):
    env.db.get_supabase_client.side_effect = ConnectionError("credentials")
    env.app.main()
    env.st.radio.assert_not_called()
    env.st.error.assert_called_once()


def test_main_permissions_error_no_navigation(env):
    env.roles.get_allowed_modules.side_effect = ValueError("access denied")
    env.app.main()
    env.st.radio.assert_not_called()
    env.st.error.assert_called_once()


def test_main_success_and_logout_button(env):
    env.st.button.return_value = True
    env.app.main()
    env.auth.logout.assert_called_once()
    env.st.radio.assert_not_called()


def test_security_route_rechecks_permission(env):
    env.roles.has_permission.return_value = False
    env.app._render_menu_page("Securite", "reader")
    env.st.error.assert_called_once_with("Accès non autorisé.")


def test_invalid_ui_choice_rejected(env):
    env.st.radio.side_effect = lambda *args, **kwargs: "Securite"
    env.roles.has_permission.return_value = False
    env.app.main()
    env.st.error.assert_called_once_with("Accès non autorisé.")


def test_session_missing_last_activity_fails_closed(env):
    env.st.session_state.pop("last_activity")
    env.app.main()
    env.auth.logout.assert_called_once()


def test_good_login_keeps_help_only(env, monkeypatch):
    env.roles.get_allowed_modules.return_value = []
    views = types.ModuleType("modules.help.views")
    views.show_help_page = Mock()
    monkeypatch.setitem(sys.modules, "modules.help", types.ModuleType("modules.help"))
    monkeypatch.setitem(sys.modules, "modules.help.views", views)
    env.app.main()
    views.show_help_page.assert_called_once()


@pytest.mark.parametrize("display_key,module_name,function", [
    ("Achats", "achats", "show_achats_page"),
    ("Stocks", "stocks", "show_stocks_page"),
    ("Production", "production", "show_production_page"),
    ("Ventes", "ventes", "show_ventes_page"),
    ("CRM", "crm", "show_crm_page"),
    ("Finance", "finance", "show_finance_page"),
    ("RH", "rh", "show_rh_page"),
    ("Dashboards", "dashboards", "show_dashboards_page"),
    ("Administration", "admin", "show_admin_page"),
])
def test_routes_continue_to_existing_views(env, monkeypatch, display_key, module_name, function):
    folder = types.ModuleType(f"modules.{module_name}")
    folder.__path__ = []
    view = types.ModuleType(f"modules.{module_name}.views")
    setattr(view, function, Mock())
    monkeypatch.setitem(sys.modules, f"modules.{module_name}", folder)
    monkeypatch.setitem(sys.modules, f"modules.{module_name}.views", view)
    env.app._render_menu_page(display_key, "Admin")
    getattr(view, function).assert_called_once()


def test_security_route_for_authorized_role(env, monkeypatch):
    folder = types.ModuleType("modules.admin")
    folder.__path__ = []
    views = types.ModuleType("modules.admin.views")
    views.show_user_management = Mock()
    monkeypatch.setitem(sys.modules, "modules.admin", folder)
    monkeypatch.setitem(sys.modules, "modules.admin.views", views)
    env.security.is_security_manager.return_value = True
    env.app._render_menu_page("Securite", "Admin")
    views.show_user_management.assert_called_once()
    env.security.is_security_manager.assert_called_once()
    env.roles.has_permission.assert_not_called()


def test_security_route_denies_admin_without_nominal_habilitation(env, monkeypatch):
    folder = types.ModuleType("modules.admin")
    folder.__path__ = []
    views = types.ModuleType("modules.admin.views")
    views.show_user_management = Mock()
    monkeypatch.setitem(sys.modules, "modules.admin", folder)
    monkeypatch.setitem(sys.modules, "modules.admin.views", views)
    env.roles.has_permission.return_value = True
    env.security.is_security_manager.return_value = False
    env.app._render_menu_page("Securite", "Admin")
    views.show_user_management.assert_not_called()
    env.st.error.assert_called_once_with("Accès non autorisé.")


def test_unknown_route_does_not_import_or_call_page(env):
    env.app._render_menu_page("ModuleInventé", "Admin")
    env.st.error.assert_not_called()


def test_exact_timeout_threshold_rejected(env):
    assert env.app._session_expired(1000 - env.app.TIMEOUT_SECONDS, 1000)
    assert env.app._session_expired(999 - env.app.TIMEOUT_SECONDS, 1000)


@pytest.mark.parametrize(
    ("elapsed", "expired"),
    [
        (0, False),
        (1799.999, False),
        (1800, True),
        (1800.001, True),
    ],
)
def test_010a_absolute_timeout_boundary(env, elapsed, expired):
    assert env.app._session_expired(5000, 5000 + elapsed) is expired


def test_010a_multiple_reruns_do_not_extend_session(env):
    env.st.session_state["last_activity"] = 1000

    for now in (1001, 1900, 2799):
        assert env.app._verified_user(now) is not None
        assert env.st.session_state["last_activity"] == 1000

    assert env.app._verified_user(2800) is None
    env.auth.logout.assert_called_once()
    assert env.db.get_supabase_client.call_count == 3


def test_010a_expired_session_does_not_query_database(env):
    env.st.session_state["last_activity"] = 1000

    assert env.app._verified_user(2800) is None

    env.auth.logout.assert_called_once()
    env.db.get_supabase_client.assert_not_called()


def test_010a_expiration_message(env):
    env.st.session_state["last_activity"] = 1000

    assert env.app._verified_user(2800) is None

    env.st.warning.assert_called_once_with(
        "Session expir\u00e9e apr\u00e8s 30 minutes. "
        "Veuillez vous reconnecter."
    )



def test_010a_navigation_callback_registered(env, monkeypatch):
    monkeypatch.setattr(env.app, "_render_menu_page", Mock())

    env.app.main()

    assert env.st.radio.call_args.kwargs["on_change"] is (
        env.app._mark_navigation_activity
    )
    assert env.st.session_state["last_activity"] == 999


def test_010a_navigation_renews_valid_session(env, monkeypatch):
    monkeypatch.setattr(env.app, "_render_menu_page", Mock())

    env.app._mark_navigation_activity()
    env.app.main()

    assert env.st.session_state["last_activity"] == 1000
    assert "_erp_navigation_changed" not in env.st.session_state
    env.auth.logout.assert_not_called()


def test_010a_navigation_cannot_revive_expired_session(env):
    env.st.session_state["last_activity"] = -800

    env.app._mark_navigation_activity()
    env.app.main()

    assert env.st.session_state["last_activity"] == -800
    env.auth.logout.assert_called_once()
    env.db.get_supabase_client.assert_not_called()


def test_010a_unauthorized_navigation_does_not_renew(env, monkeypatch):
    page = Mock()
    monkeypatch.setattr(env.app, "_render_menu_page", page)

    env.st.radio.side_effect = (
        lambda *args, **kwargs: "RubriqueInterdite"
    )

    env.app._mark_navigation_activity()
    env.app.main()

    assert env.st.session_state["last_activity"] == 999
    env.st.error.assert_called_once()
    page.assert_not_called()


def test_010a_backend_error_does_not_renew(env):
    env.db.get_supabase_client.side_effect = RuntimeError("TEST_OUTAGE")

    env.app._mark_navigation_activity()
    env.app.main()

    assert env.st.session_state["last_activity"] == 999
    env.st.error.assert_called_once()



def test_010a_stocks_activity_valid(env, monkeypatch):
    page = Mock()
    monkeypatch.setattr(env.app, "_render_menu_page", page)
    env.st.radio.side_effect = lambda *args, **kwargs: "Stocks"

    env.st.session_state["_erp_stocks_interacted"] = True
    env.app.main()

    assert env.st.session_state["last_activity"] == 1000
    assert "_erp_stocks_interacted" not in env.st.session_state
    env.auth.logout.assert_not_called()
    page.assert_called_once()


def test_010a_stocks_activity_no_event(env, monkeypatch):
    monkeypatch.setattr(env.app, "_render_menu_page", Mock())
    env.st.radio.side_effect = lambda *args, **kwargs: "Stocks"

    env.app.main()

    assert env.st.session_state["last_activity"] == 999


def test_010a_stocks_activity_expired(env):
    env.st.session_state["last_activity"] = -800
    env.st.session_state["_erp_stocks_interacted"] = True

    env.app.main()

    assert env.st.session_state["last_activity"] == -800
    assert "_erp_stocks_interacted" not in env.st.session_state
    env.auth.logout.assert_called_once()
    env.db.get_supabase_client.assert_not_called()


def test_010a_stocks_activity_wrong_module(env, monkeypatch):
    monkeypatch.setattr(env.app, "_render_menu_page", Mock())
    env.st.radio.side_effect = lambda *args, **kwargs: "Help"

    env.st.session_state["_erp_stocks_interacted"] = True
    env.app.main()

    assert env.st.session_state["last_activity"] == 999


def test_010a_stocks_activity_unauthorized(env, monkeypatch):
    page = Mock()
    monkeypatch.setattr(env.app, "_render_menu_page", page)
    env.roles.get_allowed_modules.return_value = ["Administration"]
    env.st.radio.side_effect = lambda *args, **kwargs: "Stocks"

    env.st.session_state["_erp_stocks_interacted"] = True
    env.app.main()

    assert env.st.session_state["last_activity"] == 999
    env.st.error.assert_called_once()
    page.assert_not_called()


def test_010a_stocks_activity_backend_error(env):
    env.db.get_supabase_client.side_effect = RuntimeError("TEST_OUTAGE")
    env.st.session_state["_erp_stocks_interacted"] = True

    env.app.main()

    assert env.st.session_state["last_activity"] == 999
    env.st.error.assert_called_once()



def test_010a_achats_activity_valid(env, monkeypatch):
    page = Mock()
    monkeypatch.setattr(env.app, "_render_menu_page", page)
    env.roles.get_allowed_modules.return_value = ["Achats"]
    env.st.radio.side_effect = lambda *args, **kwargs: "Achats"

    env.st.session_state["_erp_achats_interacted"] = True
    env.app.main()

    assert env.st.session_state["last_activity"] == 1000
    assert "_erp_achats_interacted" not in env.st.session_state
    env.auth.logout.assert_not_called()
    page.assert_called_once()


def test_010a_achats_activity_no_event(env, monkeypatch):
    monkeypatch.setattr(env.app, "_render_menu_page", Mock())
    env.roles.get_allowed_modules.return_value = ["Achats"]
    env.st.radio.side_effect = lambda *args, **kwargs: "Achats"

    env.app.main()

    assert env.st.session_state["last_activity"] == 999


def test_010a_achats_activity_expired(env):
    env.st.session_state["last_activity"] = -800
    env.st.session_state["_erp_achats_interacted"] = True

    env.app.main()

    assert env.st.session_state["last_activity"] == -800
    env.auth.logout.assert_called_once()
    env.db.get_supabase_client.assert_not_called()


def test_010a_achats_activity_wrong_module(env, monkeypatch):
    monkeypatch.setattr(env.app, "_render_menu_page", Mock())
    env.st.radio.side_effect = lambda *args, **kwargs: "Help"

    env.st.session_state["_erp_achats_interacted"] = True
    env.app.main()

    assert env.st.session_state["last_activity"] == 999


def test_010a_achats_activity_unauthorized(env, monkeypatch):
    page = Mock()
    monkeypatch.setattr(env.app, "_render_menu_page", page)
    env.roles.get_allowed_modules.return_value = ["Stocks"]
    env.st.radio.side_effect = lambda *args, **kwargs: "Achats"

    env.st.session_state["_erp_achats_interacted"] = True
    env.app.main()

    assert env.st.session_state["last_activity"] == 999
    env.st.error.assert_called_once()
    page.assert_not_called()


def test_010a_achats_activity_backend_error(env):
    env.db.get_supabase_client.side_effect = RuntimeError("TEST_OUTAGE")
    env.st.session_state["_erp_achats_interacted"] = True

    env.app.main()

    assert env.st.session_state["last_activity"] == 999
    env.st.error.assert_called_once()



def test_010a_production_activity_valid(env, monkeypatch):
    page = Mock()
    monkeypatch.setattr(env.app, "_render_menu_page", page)
    env.roles.get_allowed_modules.return_value = ["Production"]
    env.st.radio.side_effect = lambda *args, **kwargs: "Production"

    env.st.session_state["_erp_production_interacted"] = True
    env.app.main()

    assert env.st.session_state["last_activity"] == 1000
    assert "_erp_production_interacted" not in env.st.session_state
    env.auth.logout.assert_not_called()
    page.assert_called_once()


def test_010a_production_activity_no_event(env, monkeypatch):
    monkeypatch.setattr(env.app, "_render_menu_page", Mock())
    env.roles.get_allowed_modules.return_value = ["Production"]
    env.st.radio.side_effect = lambda *args, **kwargs: "Production"

    env.app.main()

    assert env.st.session_state["last_activity"] == 999


def test_010a_production_activity_expired(env):
    env.st.session_state["last_activity"] = -800
    env.st.session_state["_erp_production_interacted"] = True

    env.app.main()

    assert env.st.session_state["last_activity"] == -800
    assert "_erp_production_interacted" not in env.st.session_state
    env.auth.logout.assert_called_once()
    env.db.get_supabase_client.assert_not_called()


def test_010a_production_activity_wrong_module(env, monkeypatch):
    monkeypatch.setattr(env.app, "_render_menu_page", Mock())
    env.st.radio.side_effect = lambda *args, **kwargs: "Help"

    env.st.session_state["_erp_production_interacted"] = True
    env.app.main()

    assert env.st.session_state["last_activity"] == 999


def test_010a_production_activity_unauthorized(env, monkeypatch):
    page = Mock()
    monkeypatch.setattr(env.app, "_render_menu_page", page)
    env.roles.get_allowed_modules.return_value = ["Stocks"]
    env.st.radio.side_effect = lambda *args, **kwargs: "Production"

    env.st.session_state["_erp_production_interacted"] = True
    env.app.main()

    assert env.st.session_state["last_activity"] == 999
    env.st.error.assert_called_once()
    page.assert_not_called()


def test_010a_production_activity_backend_error(env):
    env.db.get_supabase_client.side_effect = RuntimeError("TEST_OUTAGE")
    env.st.session_state["_erp_production_interacted"] = True

    env.app.main()

    assert env.st.session_state["last_activity"] == 999
    env.st.error.assert_called_once()



@pytest.mark.parametrize(
    ("module", "flag"),
    [
        ("Ventes", "_erp_ventes_interacted"),
        ("CRM", "_erp_crm_interacted"),
    ],
)
def test_010a_commercial_activity_valid(env, monkeypatch, module, flag):
    page = Mock()
    monkeypatch.setattr(env.app, "_render_menu_page", page)
    env.roles.get_allowed_modules.return_value = [module]
    env.st.radio.side_effect = lambda *args, **kwargs: module

    env.st.session_state[flag] = True
    env.app.main()

    assert env.st.session_state["last_activity"] == 1000
    assert flag not in env.st.session_state
    env.auth.logout.assert_not_called()
    page.assert_called_once()


@pytest.mark.parametrize(
    ("module", "flag"),
    [
        ("Ventes", "_erp_ventes_interacted"),
        ("CRM", "_erp_crm_interacted"),
    ],
)
def test_010a_commercial_no_event(env, monkeypatch, module, flag):
    monkeypatch.setattr(env.app, "_render_menu_page", Mock())
    env.roles.get_allowed_modules.return_value = [module]
    env.st.radio.side_effect = lambda *args, **kwargs: module

    env.app.main()

    assert env.st.session_state["last_activity"] == 999
    assert flag not in env.st.session_state


@pytest.mark.parametrize(
    ("module", "flag"),
    [
        ("Ventes", "_erp_ventes_interacted"),
        ("CRM", "_erp_crm_interacted"),
    ],
)
def test_010a_commercial_expired(env, module, flag):
    env.st.session_state["last_activity"] = -800
    env.st.session_state[flag] = True

    env.app.main()

    assert env.st.session_state["last_activity"] == -800
    assert flag not in env.st.session_state
    env.auth.logout.assert_called_once()
    env.db.get_supabase_client.assert_not_called()


@pytest.mark.parametrize(
    ("module", "flag"),
    [
        ("Ventes", "_erp_ventes_interacted"),
        ("CRM", "_erp_crm_interacted"),
    ],
)
def test_010a_commercial_wrong_module(env, monkeypatch, module, flag):
    monkeypatch.setattr(env.app, "_render_menu_page", Mock())
    env.st.radio.side_effect = lambda *args, **kwargs: "Help"

    env.st.session_state[flag] = True
    env.app.main()

    assert env.st.session_state["last_activity"] == 999
    assert flag not in env.st.session_state


@pytest.mark.parametrize(
    ("module", "flag"),
    [
        ("Ventes", "_erp_ventes_interacted"),
        ("CRM", "_erp_crm_interacted"),
    ],
)
def test_010a_commercial_unauthorized(env, monkeypatch, module, flag):
    page = Mock()
    monkeypatch.setattr(env.app, "_render_menu_page", page)
    env.roles.get_allowed_modules.return_value = ["Stocks"]
    env.st.radio.side_effect = lambda *args, **kwargs: module

    env.st.session_state[flag] = True
    env.app.main()

    assert env.st.session_state["last_activity"] == 999
    env.st.error.assert_called_once()
    page.assert_not_called()


@pytest.mark.parametrize(
    ("module", "flag"),
    [
        ("Ventes", "_erp_ventes_interacted"),
        ("CRM", "_erp_crm_interacted"),
    ],
)
def test_010a_commercial_backend_error(env, module, flag):
    env.db.get_supabase_client.side_effect = RuntimeError("TEST_OUTAGE")
    env.st.session_state[flag] = True

    env.app.main()

    assert env.st.session_state["last_activity"] == 999
    assert flag not in env.st.session_state
    env.st.error.assert_called_once()



def test_010a_finance_activity_valid(env, monkeypatch):
    page = Mock()
    monkeypatch.setattr(env.app, "_render_menu_page", page)
    env.roles.get_allowed_modules.return_value = ["Finance"]
    env.st.radio.side_effect = lambda *args, **kwargs: "Finance"

    env.st.session_state["_erp_finance_interacted"] = True
    env.app.main()

    assert env.st.session_state["last_activity"] == 1000
    assert "_erp_finance_interacted" not in env.st.session_state
    env.auth.logout.assert_not_called()
    page.assert_called_once()


def test_010a_finance_activity_no_event(env, monkeypatch):
    monkeypatch.setattr(env.app, "_render_menu_page", Mock())
    env.roles.get_allowed_modules.return_value = ["Finance"]
    env.st.radio.side_effect = lambda *args, **kwargs: "Finance"

    env.app.main()

    assert env.st.session_state["last_activity"] == 999


def test_010a_finance_activity_expired(env):
    env.st.session_state["last_activity"] = -800
    env.st.session_state["_erp_finance_interacted"] = True

    env.app.main()

    assert env.st.session_state["last_activity"] == -800
    assert "_erp_finance_interacted" not in env.st.session_state
    env.auth.logout.assert_called_once()
    env.db.get_supabase_client.assert_not_called()


def test_010a_finance_activity_wrong_module(env, monkeypatch):
    monkeypatch.setattr(env.app, "_render_menu_page", Mock())
    env.st.radio.side_effect = lambda *args, **kwargs: "Help"

    env.st.session_state["_erp_finance_interacted"] = True
    env.app.main()

    assert env.st.session_state["last_activity"] == 999


def test_010a_finance_activity_unauthorized(env, monkeypatch):
    page = Mock()
    monkeypatch.setattr(env.app, "_render_menu_page", page)
    env.roles.get_allowed_modules.return_value = ["Stocks"]
    env.st.radio.side_effect = lambda *args, **kwargs: "Finance"

    env.st.session_state["_erp_finance_interacted"] = True
    env.app.main()

    assert env.st.session_state["last_activity"] == 999
    env.st.error.assert_called_once()
    page.assert_not_called()


def test_010a_finance_activity_backend_error(env):
    env.db.get_supabase_client.side_effect = RuntimeError("TEST_OUTAGE")
    env.st.session_state["_erp_finance_interacted"] = True

    env.app.main()

    assert env.st.session_state["last_activity"] == 999
    assert "_erp_finance_interacted" not in env.st.session_state
    env.st.error.assert_called_once()



def test_010a_rh_activity_valid(env, monkeypatch):
    page = Mock()
    monkeypatch.setattr(env.app, "_render_menu_page", page)
    env.roles.get_allowed_modules.return_value = ["RH"]
    env.st.radio.side_effect = lambda *args, **kwargs: "RH"

    env.st.session_state["_erp_rh_interacted"] = True
    env.app.main()

    assert env.st.session_state["last_activity"] == 1000
    assert "_erp_rh_interacted" not in env.st.session_state
    env.auth.logout.assert_not_called()
    page.assert_called_once()


def test_010a_rh_activity_no_event(env, monkeypatch):
    monkeypatch.setattr(env.app, "_render_menu_page", Mock())
    env.roles.get_allowed_modules.return_value = ["RH"]
    env.st.radio.side_effect = lambda *args, **kwargs: "RH"

    env.app.main()

    assert env.st.session_state["last_activity"] == 999


def test_010a_rh_activity_expired(env):
    env.st.session_state["last_activity"] = -800
    env.st.session_state["_erp_rh_interacted"] = True

    env.app.main()

    assert env.st.session_state["last_activity"] == -800
    assert "_erp_rh_interacted" not in env.st.session_state
    env.auth.logout.assert_called_once()
    env.db.get_supabase_client.assert_not_called()


def test_010a_rh_activity_wrong_module(env, monkeypatch):
    monkeypatch.setattr(env.app, "_render_menu_page", Mock())
    env.st.radio.side_effect = lambda *args, **kwargs: "Help"

    env.st.session_state["_erp_rh_interacted"] = True
    env.app.main()

    assert env.st.session_state["last_activity"] == 999
    assert "_erp_rh_interacted" not in env.st.session_state


def test_010a_rh_activity_unauthorized(env, monkeypatch):
    page = Mock()
    monkeypatch.setattr(env.app, "_render_menu_page", page)
    env.roles.get_allowed_modules.return_value = ["Stocks"]
    env.st.radio.side_effect = lambda *args, **kwargs: "RH"

    env.st.session_state["_erp_rh_interacted"] = True
    env.app.main()

    assert env.st.session_state["last_activity"] == 999
    env.st.error.assert_called_once()
    page.assert_not_called()


def test_010a_rh_activity_backend_error(env):
    env.db.get_supabase_client.side_effect = RuntimeError("TEST_OUTAGE")
    env.st.session_state["_erp_rh_interacted"] = True

    env.app.main()

    assert env.st.session_state["last_activity"] == 999
    assert "_erp_rh_interacted" not in env.st.session_state
    env.st.error.assert_called_once()



def test_010a_admin_activity_valid(env, monkeypatch):
    page = Mock()
    monkeypatch.setattr(env.app, "_render_menu_page", page)
    env.roles.get_allowed_modules.return_value = ["Administration"]
    env.st.radio.side_effect = lambda *args, **kwargs: "Administration"

    env.st.session_state["_erp_admin_interacted"] = True
    env.app.main()

    assert env.st.session_state["last_activity"] == 1000
    assert "_erp_admin_interacted" not in env.st.session_state
    env.auth.logout.assert_not_called()
    page.assert_called_once()


def test_010a_admin_activity_no_event(env, monkeypatch):
    monkeypatch.setattr(env.app, "_render_menu_page", Mock())
    env.roles.get_allowed_modules.return_value = ["Administration"]
    env.st.radio.side_effect = lambda *args, **kwargs: "Administration"

    env.app.main()
    assert env.st.session_state["last_activity"] == 999


def test_010a_admin_activity_expired(env):
    env.st.session_state["last_activity"] = -800
    env.st.session_state["_erp_admin_interacted"] = True

    env.app.main()

    assert env.st.session_state["last_activity"] == -800
    assert "_erp_admin_interacted" not in env.st.session_state
    env.auth.logout.assert_called_once()
    env.db.get_supabase_client.assert_not_called()


def test_010a_admin_activity_wrong_module(env, monkeypatch):
    monkeypatch.setattr(env.app, "_render_menu_page", Mock())
    env.st.radio.side_effect = lambda *args, **kwargs: "Help"

    env.st.session_state["_erp_admin_interacted"] = True
    env.app.main()

    assert env.st.session_state["last_activity"] == 999


def test_010a_admin_activity_unauthorized(env, monkeypatch):
    page = Mock()
    monkeypatch.setattr(env.app, "_render_menu_page", page)
    env.roles.get_allowed_modules.return_value = ["Stocks"]
    env.st.radio.side_effect = lambda *args, **kwargs: "Administration"

    env.st.session_state["_erp_admin_interacted"] = True
    env.app.main()

    assert env.st.session_state["last_activity"] == 999
    env.st.error.assert_called_once()
    page.assert_not_called()


def test_010a_admin_activity_backend_error(env):
    env.db.get_supabase_client.side_effect = RuntimeError("TEST_OUTAGE")
    env.st.session_state["_erp_admin_interacted"] = True

    env.app.main()

    assert env.st.session_state["last_activity"] == 999
    assert "_erp_admin_interacted" not in env.st.session_state
    env.st.error.assert_called_once()



def test_010a_dashboards_activity_valid(env, monkeypatch):
    page = Mock()
    monkeypatch.setattr(env.app, "_render_menu_page", page)
    env.roles.get_allowed_modules.return_value = ["Dashboards"]
    env.st.radio.side_effect = lambda *args, **kwargs: "Dashboards"

    env.st.session_state["_erp_dashboards_interacted"] = True
    env.app.main()

    assert env.st.session_state["last_activity"] == 1000
    assert "_erp_dashboards_interacted" not in env.st.session_state
    env.auth.logout.assert_not_called()
    page.assert_called_once()


def test_010a_dashboards_activity_no_event(env, monkeypatch):
    monkeypatch.setattr(env.app, "_render_menu_page", Mock())
    env.roles.get_allowed_modules.return_value = ["Dashboards"]
    env.st.radio.side_effect = lambda *args, **kwargs: "Dashboards"

    env.app.main()

    assert env.st.session_state["last_activity"] == 999


def test_010a_dashboards_activity_expired(env):
    env.st.session_state["last_activity"] = -800
    env.st.session_state["_erp_dashboards_interacted"] = True

    env.app.main()

    assert env.st.session_state["last_activity"] == -800
    assert "_erp_dashboards_interacted" not in env.st.session_state
    env.auth.logout.assert_called_once()
    env.db.get_supabase_client.assert_not_called()


def test_010a_dashboards_activity_wrong_module(env, monkeypatch):
    monkeypatch.setattr(env.app, "_render_menu_page", Mock())
    env.st.radio.side_effect = lambda *args, **kwargs: "Help"

    env.st.session_state["_erp_dashboards_interacted"] = True
    env.app.main()

    assert env.st.session_state["last_activity"] == 999
    assert "_erp_dashboards_interacted" not in env.st.session_state


def test_010a_dashboards_activity_unauthorized(env, monkeypatch):
    page = Mock()
    monkeypatch.setattr(env.app, "_render_menu_page", page)
    env.roles.get_allowed_modules.return_value = ["Stocks"]
    env.st.radio.side_effect = lambda *args, **kwargs: "Dashboards"

    env.st.session_state["_erp_dashboards_interacted"] = True
    env.app.main()

    assert env.st.session_state["last_activity"] == 999
    env.st.error.assert_called_once()
    page.assert_not_called()


def test_010a_dashboards_activity_backend_error(env):
    env.db.get_supabase_client.side_effect = RuntimeError("TEST_OUTAGE")
    env.st.session_state["_erp_dashboards_interacted"] = True

    env.app.main()

    assert env.st.session_state["last_activity"] == 999
    assert "_erp_dashboards_interacted" not in env.st.session_state
    env.st.error.assert_called_once()



def test_010a_help_activity_valid(env, monkeypatch):
    page = Mock()
    monkeypatch.setattr(env.app, "_render_menu_page", page)
    env.st.radio.side_effect = lambda *args, **kwargs: "Help"

    env.st.session_state["_erp_help_interacted"] = True
    env.app.main()

    assert env.st.session_state["last_activity"] == 1000
    assert "_erp_help_interacted" not in env.st.session_state
    env.auth.logout.assert_not_called()
    page.assert_called_once()


def test_010a_help_activity_no_event(env, monkeypatch):
    monkeypatch.setattr(env.app, "_render_menu_page", Mock())
    env.st.radio.side_effect = lambda *args, **kwargs: "Help"

    env.app.main()

    assert env.st.session_state["last_activity"] == 999


def test_010a_help_activity_expired(env):
    env.st.session_state["last_activity"] = -800
    env.st.session_state["_erp_help_interacted"] = True

    env.app.main()

    assert env.st.session_state["last_activity"] == -800
    assert "_erp_help_interacted" not in env.st.session_state
    env.auth.logout.assert_called_once()
    env.db.get_supabase_client.assert_not_called()


def test_010a_help_activity_wrong_module(env, monkeypatch):
    monkeypatch.setattr(env.app, "_render_menu_page", Mock())
    env.st.radio.side_effect = lambda *args, **kwargs: "Stocks"

    env.st.session_state["_erp_help_interacted"] = True
    env.app.main()

    assert env.st.session_state["last_activity"] == 999
    assert "_erp_help_interacted" not in env.st.session_state


def test_010a_help_activity_unauthorized(env, monkeypatch):
    page = Mock()
    monkeypatch.setattr(env.app, "_render_menu_page", page)
    env.roles.get_allowed_modules.return_value = ["Stocks"]
    env.st.radio.side_effect = lambda *args, **kwargs: "Securite"

    env.st.session_state["_erp_help_interacted"] = True
    env.app.main()

    assert env.st.session_state["last_activity"] == 999
    env.st.error.assert_called_once()
    page.assert_not_called()


def test_010a_help_activity_backend_error(env):
    env.db.get_supabase_client.side_effect = RuntimeError("TEST_OUTAGE")
    env.st.session_state["_erp_help_interacted"] = True

    env.app.main()

    assert env.st.session_state["last_activity"] == 999
    assert "_erp_help_interacted" not in env.st.session_state
    env.st.error.assert_called_once()
