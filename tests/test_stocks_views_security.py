"""Tests isolés de la vue Stocks : aucune connexion à Supabase réelle."""
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest


VIEW_PATH = Path(__file__).resolve().parents[1] / "modules" / "stocks" / "views.py"


@pytest.fixture
def ui(monkeypatch):
    st = MagicMock()
    st.session_state = {"authenticated": True, "user": {"user_id": "USR-1", "role": "ADMIN"}}
    st.tabs.side_effect = lambda labels: [MagicMock() for _ in labels]
    st.columns.return_value = [MagicMock(), MagicMock()]
    st.radio.return_value = "🧪 Matière Première (Vrac)"
    st.form_submit_button.return_value = False
    st.button.return_value = False
    st.columns.return_value[0].selectbox.return_value = "MP-1"
    st.columns.return_value[1].number_input.return_value = 10.0
    st.columns.return_value[0].number_input.return_value = 2.5
    st.columns.return_value[1].text_input.return_value = "AJUST-2026-1"
    st.columns.return_value[0].date_input.return_value = "2028-01-01"

    client = MagicMock()
    query = client.table.return_value.select.return_value.eq.return_value.limit.return_value
    query.execute.return_value = types.SimpleNamespace(
        data=[{"user_id": "USR-1", "role": "MAGASINIER", "actif": "OUI"}]
    )
    db = types.ModuleType("core.db_service")
    db.fetch_data = MagicMock(return_value=[])
    db.get_supabase_client = MagicMock(return_value=client)

    roles = types.ModuleType("config.roles")
    roles.has_permission = MagicMock(side_effect=lambda role, module, kind: role == "MAGASINIER")

    stocks = types.ModuleType("modules.stocks.service")
    stocks.enregistrer_entree_mp = MagicMock()
    for name in ("get_mouvements", "get_mouvements_pf", "get_stock_actuel_mp", "get_stock_actuel_pf"):
        setattr(stocks, name, MagicMock(return_value=pd.DataFrame()))
    class StockOperationError(RuntimeError):
        def __init__(self, message, operation_id):
            super().__init__(message)
            self.operation_id = operation_id
    stocks.StockOperationError = StockOperationError

    for key, obj in {
        "streamlit": st,
        "config": types.ModuleType("config"),
        "config.roles": roles,
        "core": types.ModuleType("core"),
        "core.db_service": db,
        "modules": types.ModuleType("modules"),
        "modules.stocks": types.ModuleType("modules.stocks"),
        "modules.stocks.service": stocks,
    }.items():
        monkeypatch.setitem(sys.modules, key, obj)
    spec = importlib.util.spec_from_file_location("secure_stocks_views_under_test", VIEW_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return types.SimpleNamespace(mod=mod, st=st, db=db, client=client, roles=roles, stocks=stocks, query=query)


def _valid_mp(ui):
    ui.mod.get_mp_actives = MagicMock(return_value=pd.DataFrame([{
        "mp_id": "MP-1", "nom": "Pigment", "categorie_mp": "PIGMENT_COLORANT",
        "unite_stock": "Kg", "stock_mini": 0,
    }]))


def _payload():
    return {"mp_id": "MP-1", "quantite": 10.0, "prix_entree": 2.5,
            "reference": "AJUST-2026-1", "date_peremption": "2028-01-01"}


@pytest.mark.parametrize("authenticated, user", [
    (False, {"user_id": "USR-1"}),
    (True, None),
    (True, {}),
    (True, {"user_id": ""}),
    (True, {"user_id": 123}),
])
def test_denied_sessions_do_not_read_stock(ui, authenticated, user):
    ui.st.session_state = {"authenticated": authenticated, "user": user}
    ui.mod.show_stocks_page()
    ui.db.fetch_data.assert_not_called()
    ui.st.tabs.assert_not_called()
    ui.st.error.assert_called()


@pytest.mark.parametrize("record", [
    [],
    [{"user_id": "USR-1", "role": "MAGASINIER", "actif": "NON"}],
    [{"user_id": "USR-2", "role": "ADMIN", "actif": "OUI"}],
    [{"user_id": "USR-1", "role": "", "actif": "OUI"}],
    [{"user_id": "USR-1", "role": "MAGASINIER", "actif": "OUI"}] * 2,
])
def test_denied_accounts_do_not_read_stock(ui, record):
    ui.query.execute.return_value = types.SimpleNamespace(data=record)
    ui.mod.show_stocks_page()
    ui.db.fetch_data.assert_not_called()
    ui.st.tabs.assert_not_called()


def test_database_error_denies_read(ui):
    ui.query.execute.side_effect = RuntimeError("db unavailable")
    ui.mod.show_stocks_page()
    ui.db.fetch_data.assert_not_called()


def test_stale_session_admin_role_cannot_override_actual_role(ui):
    ui.roles.has_permission.side_effect = lambda role, module, kind: False
    ui.mod.show_stocks_page()
    ui.roles.has_permission.assert_called_once_with("MAGASINIER", "Stocks", "lecture")
    ui.db.fetch_data.assert_not_called()


def test_readonly_user_can_see_stock_but_not_entry_form(ui):
    ui.roles.has_permission.side_effect = lambda role, module, kind: kind == "lecture"
    _valid_mp(ui)
    ui.mod.show_stocks_page()
    ui.mod.get_mp_actives.assert_called_once()
    ui.st.form.assert_not_called()
    ui.st.warning.assert_called()
    ui.st.session_state.get("stocks_entree_manuelle_USR-1") is None


def test_successful_entry_preserves_confirmation_and_blocks_duplicate(ui):
    _valid_mp(ui)
    ui.st.form_submit_button.return_value = True
    ui.mod.show_stocks_page()
    key = ui.mod._entry_key("USR-1")
    record = ui.st.session_state[key]
    assert record["status"] == "confirmed"
    assert record["operation_id"].startswith("STK-MAN-")
    assert record["payload"] == _payload()
    args, kwargs = ui.stocks.enregistrer_entree_mp.call_args
    assert args == ("MP-1", 10.0, 2.5, "AJUST-2026-1", "2028-01-01")
    assert kwargs == {"operation_id": record["operation_id"]}
    ui.st.cache_data.clear.assert_called_once()
    ui.st.rerun.assert_called_once()
    # Second rerun: the submitted form is not visible until explicitly reset.
    ui.st.form.reset_mock()
    ui.mod.show_stocks_page()
    assert ui.stocks.enregistrer_entree_mp.call_count == 1
    ui.st.form.assert_not_called()
    ui.st.success.assert_called()


def test_uncertain_entry_retries_exactly_same_payload_and_id(ui):
    _valid_mp(ui)
    ui.st.form_submit_button.return_value = True
    ui.stocks.enregistrer_entree_mp.side_effect = RuntimeError("network timeout")
    ui.mod.show_stocks_page()
    record = ui.st.session_state[ui.mod._entry_key("USR-1")]
    assert record["status"] == "uncertain"
    original_id = record["operation_id"]
    first_call = ui.stocks.enregistrer_entree_mp.call_args
    ui.st.form.reset_mock()
    ui.st.form_submit_button.return_value = True
    ui.st.button.return_value = True
    ui.stocks.enregistrer_entree_mp.side_effect = None
    ui.st.columns.return_value[1].number_input.return_value = 999
    ui.mod.show_stocks_page()
    assert ui.stocks.enregistrer_entree_mp.call_count == 2
    assert ui.stocks.enregistrer_entree_mp.call_args == first_call
    assert record["status"] == "confirmed"
    assert record["operation_id"] == original_id
    ui.st.form.assert_not_called()


def test_stock_operation_error_keeps_same_id(ui):
    _valid_mp(ui)
    ui.st.form_submit_button.return_value = True
    def fail(*args, **kwargs):
        raise ui.stocks.StockOperationError("unknown commit", kwargs["operation_id"])
    ui.stocks.enregistrer_entree_mp.side_effect = fail
    ui.mod.show_stocks_page()
    record = ui.st.session_state[ui.mod._entry_key("USR-1")]
    assert record["status"] == "uncertain"
    assert record["operation_id"] in str(ui.st.code.call_args)


def test_pending_entry_does_not_auto_retry(ui):
    _valid_mp(ui)
    ui.st.session_state[ui.mod._entry_key("USR-1")] = {
        "operation_id": "STK-MAN-PENDING", "payload": _payload(), "status": "uncertain"
    }
    ui.mod.show_stocks_page()
    ui.stocks.enregistrer_entree_mp.assert_not_called()
    ui.st.form.assert_not_called()


def test_confirmed_requires_explicit_new_entry(ui):
    _valid_mp(ui)
    key = ui.mod._entry_key("USR-1")
    ui.st.session_state[key] = {
        "operation_id": "STK-MAN-DONE", "payload": _payload(), "status": "confirmed"
    }
    ui.st.button.return_value = True
    ui.mod.show_stocks_page()
    assert key not in ui.st.session_state
    ui.st.rerun.assert_called_once()
    ui.stocks.enregistrer_entree_mp.assert_not_called()


def test_same_browser_other_user_cannot_see_prior_pending_entry(ui):
    ui.st.session_state[ui.mod._entry_key("USR-1")] = {
        "operation_id": "STK-MAN-OLD", "payload": _payload(), "status": "uncertain"
    }
    ui.st.session_state["user"] = {"user_id": "USR-2", "role": "MAGASINIER"}
    ui.query.execute.return_value = types.SimpleNamespace(
        data=[{"user_id": "USR-2", "role": "MAGASINIER", "actif": "OUI"}]
    )
    _valid_mp(ui)
    ui.mod.show_stocks_page()
    ui.st.form.assert_called_once()
    ui.st.code.assert_not_called()


def test_missing_reference_does_not_create_pending_operation(ui):
    _valid_mp(ui)
    ui.st.form_submit_button.return_value = True
    ui.st.columns.return_value[1].text_input.return_value = "  "
    ui.mod.show_stocks_page()
    ui.stocks.enregistrer_entree_mp.assert_not_called()
    assert ui.mod._entry_key("USR-1") not in ui.st.session_state
    ui.st.error.assert_called()


def test_denied_write_cannot_retry_old_pending_operation(ui):
    _valid_mp(ui)
    ui.roles.has_permission.side_effect = lambda role, module, kind: kind == "lecture"
    ui.st.session_state[ui.mod._entry_key("USR-1")] = {
        "operation_id": "STK-MAN-PENDING", "payload": _payload(), "status": "uncertain"
    }
    ui.st.button.return_value = True
    ui.mod.show_stocks_page()
    ui.stocks.enregistrer_entree_mp.assert_not_called()
    ui.st.button.assert_not_called()


def test_malformed_state_stays_locked(ui):
    _valid_mp(ui)
    ui.st.session_state[ui.mod._entry_key("USR-1")] = {"status": "bad"}
    ui.mod.show_stocks_page()
    ui.st.form.assert_not_called()
    ui.st.error.assert_called()


def test_rpc_is_not_bypassed_in_view(ui):
    source = VIEW_PATH.read_text(encoding="utf-8")
    assert "enregistrer_entree_mp(" in source
    assert ".rpc(" not in source
    assert "operation_id=operation_id" in source


@pytest.mark.parametrize("exception", [ValueError("reference too long"), PermissionError("revoked")])
def test_validation_or_permission_error_releases_form_without_retry_id(ui, exception):
    _valid_mp(ui)
    ui.st.form_submit_button.return_value = True
    ui.stocks.enregistrer_entree_mp.side_effect = exception
    ui.mod.show_stocks_page()
    assert ui.mod._entry_key("USR-1") not in ui.st.session_state
    ui.st.code.assert_not_called()
    ui.st.error.assert_called()
