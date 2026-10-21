"""Tests écran Achats isolés : aucun accès réseau ni base réelle."""
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest


VIEW_PATH = Path(__file__).resolve().parents[1] / "modules" / "achats" / "views.py"


def _mk_col(st):
    col = MagicMock()
    col.radio.side_effect = lambda *args, **kwargs: st.radio(*args, **kwargs)
    return col


@pytest.fixture
def ui(monkeypatch):
    st = MagicMock()
    st.session_state = {"authenticated": True, "user": {"user_id": "USR-1", "role": "ADMIN"}}
    st.tabs.side_effect = lambda labels: [MagicMock() for _ in labels]
    st.columns.side_effect = lambda count: [_mk_col(st) for _ in range(count if isinstance(count, int) else len(count))]
    st.form_submit_button.return_value = False
    st.button.return_value = False
    st.selectbox.return_value = "CMA-1"
    st.number_input.return_value = 5.0
    st.radio.return_value = "CONFORME"
    st.date_input.return_value = "2026-10-21"

    client = MagicMock()
    query = client.table.return_value.select.return_value.eq.return_value.limit.return_value
    query.execute.return_value = types.SimpleNamespace(
        data=[{"user_id": "USR-1", "role": "ACHETEUR", "actif": "OUI"}])
    db = types.ModuleType("core.db_service")
    db.get_supabase_client = MagicMock(return_value=client)
    db.fetch_data = MagicMock(return_value=[])

    roles = types.ModuleType("config.roles")
    roles.has_permission = MagicMock(return_value=True)

    listes = types.ModuleType("core.listes_service")
    listes.get_liste = MagicMock(return_value=[])
    listes.liste_to_dict = MagicMock(return_value={})

    utils = types.ModuleType("core.utils")
    utils.get_local_now = MagicMock(return_value="2026-10-21")

    achats = types.ModuleType("modules.achats.service")
    for name in ("create_commande_achat", "creer_bon_reception", "get_commandes",
                 "get_bons_reception", "get_lignes_achats", "get_lignes_bons_reception"):
        setattr(achats, name, MagicMock())
    achats.create_commande_achat.return_value = "CMA-1"
    achats.creer_bon_reception.return_value = "BR-1"
    achats.get_commandes.return_value = pd.DataFrame()
    achats.get_bons_reception.return_value = pd.DataFrame()
    achats.get_lignes_achats.return_value = pd.DataFrame()
    achats.get_lignes_bons_reception.return_value = pd.DataFrame()

    for key, obj in {
        "streamlit": st,
        "config": types.ModuleType("config"),
        "config.roles": roles,
        "core": types.ModuleType("core"),
        "core.db_service": db,
        "core.listes_service": listes,
        "core.utils": utils,
        "modules": types.ModuleType("modules"),
        "modules.achats": types.ModuleType("modules.achats"),
        "modules.achats.service": achats,
    }.items():
        monkeypatch.setitem(sys.modules, key, obj)
    spec = importlib.util.spec_from_file_location("achats_views_under_test", VIEW_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return types.SimpleNamespace(mod=mod, st=st, db=db, client=client, query=query,
                                 roles=roles, achats=achats)


def _sample_order():
    return pd.DataFrame([{
        "commande_achat_id": "CMA-1", "statut": "PARTIELLEMENT_RECEPTIONNE",
        "fournisseur_id": "FRN-1", "date_commande": "2026-10-10"}])


def _sample_lines():
    return pd.DataFrame([{"mp_id": "MP-1", "qte_totale": 100, "prix_unitaire": 12}])


def _sample_brs():
    return pd.DataFrame([{"bon_reception_id": "BR-1", "commande_achat_id": "CMA-1", "date_reception": "2026-10-20"}])


def _sample_recv(qty=40):
    return pd.DataFrame([{"mp_id": "MP-1", "quantite_recue": qty}])


def _configure_received(ui, qty=40):
    ui.achats.get_commandes.return_value = _sample_order()
    ui.achats.get_lignes_achats.return_value = _sample_lines()
    ui.achats.get_bons_reception.return_value = _sample_brs()
    ui.achats.get_lignes_bons_reception.return_value = _sample_recv(qty)


def _order_payload():
    return {
        "fournisseur_id": "FRN-1", "type_achat": "Matière Première", "devise": "DZD",
        "taux_change": 1., "mode_paiement": "Virement", "delai_paiement": "30 jours",
        "date_voulue": "2026-11-01", "panier": [{"mp_id": "MP-1", "nom_article": "MP",
              "unite_cond": "Kg", "qte_cond": 10., "qte_totale": 10.,
              "prix_unitaire": 2., "total_devise": 20.}],
    }


def _receipt_payload():
    return {"commande_achat_id": "CMA-1", "date_reception": "2026-10-21",
            "controle_conformite": "OUI", "remarques": "", "date_peremption": "2028-01-01",
            "items_recus": [{"mp_id": "MP-1", "quantite_recue": 60., "prix_unitaire": 12.}]}


@pytest.mark.parametrize("authenticated,user", [
    (False, {"user_id": "USR-1"}), (True, None), (True, {}),
    (True, {"user_id": ""}), (True, {"user_id": 1}),
])
def test_invalid_sessions_never_read_business_data(ui, authenticated, user):
    ui.st.session_state = {"authenticated": authenticated, "user": user}
    ui.mod.show_achats_page()
    ui.achats.get_commandes.assert_not_called()
    ui.db.fetch_data.assert_not_called()
    ui.st.tabs.assert_not_called()


@pytest.mark.parametrize("accounts", [
    [], [{"user_id": "USR-2", "role": "ACHETEUR", "actif": "OUI"}],
    [{"user_id": "USR-1", "role": "ACHETEUR", "actif": "NON"}],
    [{"user_id": "USR-1", "role": "", "actif": "OUI"}],
    [{"user_id": "USR-1", "role": "ACHETEUR", "actif": "OUI"}]*2,
])
def test_db_denied_accounts_never_read_business_data(ui, accounts):
    ui.query.execute.return_value = types.SimpleNamespace(data=accounts)
    ui.mod.show_achats_page()
    ui.achats.get_commandes.assert_not_called()
    ui.db.fetch_data.assert_not_called()


def test_db_error_fail_closed(ui):
    ui.query.execute.side_effect = RuntimeError("db outage")
    ui.mod.show_achats_page()
    ui.st.tabs.assert_not_called()


def test_stale_session_role_cannot_grant_read(ui):
    ui.roles.has_permission.return_value = False
    ui.mod.show_achats_page()
    ui.roles.has_permission.assert_called_once_with("ACHETEUR", "Achats", "lecture")
    ui.st.tabs.assert_not_called()


def test_read_only_role_can_view_history_not_write(ui):
    ui.roles.has_permission.side_effect = lambda role, module, permission: permission == "lecture"
    ui.mod.show_achats_page()
    ui.achats.create_commande_achat.assert_not_called()
    ui.achats.creer_bon_reception.assert_not_called()
    ui.achats.get_commandes.assert_called()
    ui.st.form.assert_not_called()


def test_purchase_access_uses_current_db_role(ui):
    assert ui.mod._purchase_access() == ("USR-1", True)
    assert ui.roles.has_permission.call_args_list[0].args == ("ACHETEUR", "Achats", "lecture")


def test_empty_receipts_uses_full_order(ui):
    got = ui.mod._remaining_quantities("CMA-1", _sample_lines(), pd.DataFrame())
    assert got[0]["remaining"] == 100
    ui.achats.get_lignes_bons_reception.assert_not_called()


def test_partially_received_is_subtracted(ui):
    _configure_received(ui)
    got = ui.mod._remaining_quantities("CMA-1", _sample_lines(), _sample_brs())
    assert got == [{"mp_id": "MP-1", "ordered": 100., "received": 40.,
                    "remaining": 60., "prix_unitaire": 12.}]


def test_other_orders_receipts_ignored(ui):
    brs = pd.DataFrame([{"bon_reception_id": "BR-X", "commande_achat_id": "CMA-X"}])
    got = ui.mod._remaining_quantities("CMA-1", _sample_lines(), brs)
    assert got[0]["remaining"] == 100
    ui.achats.get_lignes_bons_reception.assert_not_called()


def test_duplicate_mp_lines_aggregated_and_weighted_price(ui):
    lines = pd.DataFrame([{"mp_id": "MP-1", "qte_totale": 40, "prix_unitaire": 2},
                          {"mp_id": "MP-1", "qte_totale": 60, "prix_unitaire": 4}])
    got = ui.mod._remaining_quantities("CMA-1", lines, pd.DataFrame())
    assert len(got) == 1
    assert got[0]["ordered"] == 100
    assert got[0]["prix_unitaire"] == 3.2


@pytest.mark.parametrize("data", [
    pd.DataFrame(),
    pd.DataFrame([{"mp_id": "MP-1", "prix_unitaire": 2}]),
    pd.DataFrame([{"mp_id": "MP-1", "qte_totale": -1, "prix_unitaire": 2}]),
    pd.DataFrame([{"mp_id": "MP-1", "qte_totale": float("nan"), "prix_unitaire": 2}]),
    pd.DataFrame([{"mp_id": "MP-1", "qte_totale": 1, "prix_unitaire": -1}]),
])
def test_invalid_order_lines_block_receipt(ui, data):
    with pytest.raises(ValueError):
        ui.mod._remaining_quantities("CMA-1", data, pd.DataFrame())


def test_missing_receipt_history_blocks_reception(ui):
    ui.achats.get_lignes_bons_reception.return_value = pd.DataFrame()
    with pytest.raises(ValueError):
        ui.mod._remaining_quantities("CMA-1", _sample_lines(), _sample_brs())


def test_over_received_history_blocks_reception(ui):
    _configure_received(ui, qty=101)
    with pytest.raises(ValueError):
        ui.mod._remaining_quantities("CMA-1", _sample_lines(), _sample_brs())


def test_fully_received_returns_no_items(ui):
    _configure_received(ui, qty=100)
    assert ui.mod._remaining_quantities("CMA-1", _sample_lines(), _sample_brs()) == []


def test_partial_order_visible_in_ui(ui):
    _configure_received(ui)
    ui.st.selectbox.return_value = "CMA-1"
    ui.mod.show_achats_page()
    ui.achats.get_lignes_achats.assert_called_once_with("CMA-1")
    ui.achats.get_lignes_bons_reception.assert_called_once_with("BR-1")
    assert any("PARTIELLEMENT_RECEPTIONNE" in str(x) for x in ui.achats.get_commandes.return_value["statut"])


def test_start_purchase_captures_payload_before_rpc(ui):
    payload = _order_payload()
    ui.mod._start_operation("commande", "USR-1", payload)
    key = ui.mod._operation_key("commande", "USR-1")
    rec = ui.st.session_state[key]
    assert rec["status"] == "confirmed"
    assert rec["operation_id"].startswith("ACH-UI-")
    assert rec["document_id"] == "CMA-1"
    assert ui.achats.create_commande_achat.call_args.kwargs["operation_id"] == rec["operation_id"]
    assert ui.st.session_state[ui.mod._cart_key("USR-1")] == []


def test_successful_receipt_is_confirmed(ui):
    ui.mod._start_operation("reception", "USR-1", _receipt_payload())
    rec = ui.st.session_state[ui.mod._operation_key("reception", "USR-1")]
    assert rec["status"] == "confirmed" and rec["document_id"] == "BR-1"
    ui.achats.creer_bon_reception.assert_called_once()
    assert ui.achats.creer_bon_reception.call_args.kwargs["controle_conformite"] == "OUI"


def test_unknown_network_result_keeps_same_id_and_frozen_payload(ui):
    ui.achats.create_commande_achat.side_effect = RuntimeError("timeout")
    payload = _order_payload()
    ui.mod._start_operation("commande", "USR-1", payload)
    record = ui.st.session_state[ui.mod._operation_key("commande", "USR-1")]
    assert record["status"] == "uncertain"
    old_id = record["operation_id"]
    original_call = ui.achats.create_commande_achat.call_args
    payload["panier"][0]["qte_totale"] = 999
    ui.achats.create_commande_achat.side_effect = None
    ui.mod._execute_operation("commande", "USR-1")
    assert ui.achats.create_commande_achat.call_count == 2
    assert ui.achats.create_commande_achat.call_args == original_call
    assert record["operation_id"] == old_id
    assert record["status"] == "confirmed"


def test_bad_rpc_result_remains_uncertain(ui):
    ui.achats.creer_bon_reception.return_value = None
    ui.mod._start_operation("reception", "USR-1", _receipt_payload())
    record = ui.st.session_state[ui.mod._operation_key("reception", "USR-1")]
    assert record["status"] == "uncertain"


def test_pre_rpc_validation_error_can_be_corrected(ui):
    ui.achats.create_commande_achat.side_effect = ValueError("Invalid order")
    ui.mod._start_operation("commande", "USR-1", _order_payload())
    assert ui.mod._operation_key("commande", "USR-1") not in ui.st.session_state
    ui.achats.create_commande_achat.assert_called_once()


def test_denied_write_is_not_sent_to_rpc(ui):
    ui.roles.has_permission.side_effect = lambda role, module, permission: permission == "lecture"
    ui.mod.show_achats_page()
    ui.achats.creer_bon_reception.assert_not_called()
    ui.achats.create_commande_achat.assert_not_called()


def test_second_start_does_not_replace_uncertain_order(ui):
    ui.achats.create_commande_achat.side_effect = RuntimeError("timeout")
    ui.mod._start_operation("commande", "USR-1", _order_payload())
    old_record = ui.st.session_state[ui.mod._operation_key("commande", "USR-1")]
    ui.mod._start_operation("commande", "USR-1", _order_payload())
    assert ui.achats.create_commande_achat.call_count == 1
    assert ui.st.session_state[ui.mod._operation_key("commande", "USR-1")] is old_record


def test_pending_panel_retries_identical_operation(ui):
    ui.achats.creer_bon_reception.side_effect = RuntimeError("timeout")
    ui.mod._start_operation("reception", "USR-1", _receipt_payload())
    previous = ui.achats.creer_bon_reception.call_args
    ui.achats.creer_bon_reception.side_effect = None
    ui.st.button.return_value = True
    assert ui.mod._pending_panel("reception", "USR-1") is True
    assert ui.achats.creer_bon_reception.call_count == 2
    assert ui.achats.creer_bon_reception.call_args == previous


def test_invalid_pending_state_blocks_creation(ui):
    ui.st.session_state[ui.mod._operation_key("reception", "USR-1")] = {"status": "unknown"}
    assert ui.mod._pending_panel("reception", "USR-1") is True
    ui.achats.creer_bon_reception.assert_not_called()


def test_confirmed_pending_requires_explicit_new_action(ui):
    ui.mod._start_operation("commande", "USR-1", _order_payload())
    assert ui.mod._pending_panel("commande", "USR-1") is True
    ui.achats.create_commande_achat.assert_called_once()


def test_purchase_and_receipt_state_are_isolated(ui):
    ui.mod._start_operation("commande", "USR-1", _order_payload())
    ui.mod._start_operation("reception", "USR-1", _receipt_payload())
    assert ui.mod._operation_key("commande", "USR-1") in ui.st.session_state
    assert ui.mod._operation_key("reception", "USR-1") in ui.st.session_state
    assert ui.mod._operation_key("commande", "USR-1") != ui.mod._operation_key("reception", "USR-1")


def test_receipt_ui_conforme_calls_service_with_oui(ui):
    _configure_received(ui)
    ui.st.selectbox.return_value = "CMA-1"
    ui.st.form_submit_button.return_value = True
    ui.st.radio.return_value = "CONFORME"
    ui.mod.show_achats_page()
    assert ui.achats.creer_bon_reception.call_count == 1
    data = ui.achats.creer_bon_reception.call_args.kwargs
    assert data["controle_conformite"] == "OUI"
    assert data["items_recus"][0]["mp_id"] == "MP-1"
    assert data["operation_id"].startswith("ACH-UI-")


@pytest.mark.parametrize("selection", ["RESERVE", "NON_CONFORME"])
def test_receipt_non_conforme_never_credits_stock(ui, selection):
    _configure_received(ui)
    ui.st.selectbox.return_value = "CMA-1"
    ui.st.form_submit_button.return_value = True
    ui.st.radio.return_value = selection
    ui.mod.show_achats_page()
    ui.achats.creer_bon_reception.assert_not_called()
    ui.st.error.assert_called()


def test_receipt_all_zero_quantities_prevents_rpc(ui):
    _configure_received(ui)
    ui.st.selectbox.return_value = "CMA-1"
    ui.st.form_submit_button.return_value = True
    ui.st.number_input.return_value = 0.
    ui.mod.show_achats_page()
    ui.achats.creer_bon_reception.assert_not_called()
    ui.st.error.assert_called()


def test_corrupted_receipt_history_blocks_rpc(ui):
    _configure_received(ui, qty=101)
    ui.st.selectbox.return_value = "CMA-1"
    ui.st.form_submit_button.return_value = True
    ui.mod.show_achats_page()
    ui.achats.creer_bon_reception.assert_not_called()
    ui.st.error.assert_called()


def test_carts_isolated_by_user(ui):
    key1 = ui.mod._cart_key("USR-1")
    key2 = ui.mod._cart_key("USR-2")
    assert key1 != key2
    ui.st.session_state[key1] = [{"mp_id": "MP-1"}]
    ui.st.session_state[key2] = [{"mp_id": "MP-2"}]
    assert ui.st.session_state[key2] == [{"mp_id": "MP-2"}]


def test_confirmed_record_missing_document_blocks_gracefully(ui):
    ui.st.session_state[ui.mod._operation_key("commande", "USR-1")] = {
        "status": "confirmed", "operation_id": "ACH-UI-abc", "payload": _order_payload()}
    assert ui.mod._pending_panel("commande", "USR-1") is True
    ui.st.error.assert_called()
    ui.achats.create_commande_achat.assert_not_called()
