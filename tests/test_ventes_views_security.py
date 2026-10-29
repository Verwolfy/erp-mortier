"""Tests hors réseau et sans Supabase réel : interface Ventes transactionnelle."""
import importlib.util
import sys
import types
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest


VIEW = Path(__file__).resolve().parents[1] / "modules" / "ventes" / "views.py"


@pytest.fixture
def ui(monkeypatch):
    st = MagicMock()
    st.session_state = {"authenticated": True, "user": {"user_id": "USR-1", "role": "VENDEUR"}}
    st.tabs.side_effect = lambda labels: [MagicMock() for _ in labels]
    st.form_submit_button.return_value = False
    st.button.return_value = False
    st.selectbox.side_effect = lambda label, options, **kw: options[0]
    st.date_input.return_value = "2026-10-21"
    st.number_input.return_value = 0.0
    st.checkbox.return_value = False
    st.text_input.return_value = ""

    client = MagicMock()
    query = client.table.return_value.select.return_value.eq.return_value.limit.return_value
    query.execute.return_value = types.SimpleNamespace(
        data=[{"user_id": "USR-1", "role": "VENDEUR", "actif": "OUI"}])
    db = types.ModuleType("core.db_service")
    db.get_supabase_client = MagicMock(return_value=client)
    db.fetch_data_paginated = MagicMock(return_value=[])
    roles = types.ModuleType("config.roles")
    roles.has_permission = MagicMock(return_value=True)

    sales = types.ModuleType("modules.ventes.service")
    for name in ("annuler_facture", "calculer_montants_facture", "create_facture_brouillon",
                 "creer_bon_livraison", "creer_commande_client", "get_factures", "get_lignes_facture", "valider_facture"):
        setattr(sales, name, MagicMock())
    sales.get_factures.return_value = pd.DataFrame()
    sales.create_facture_brouillon.return_value = "FAC-1"
    sales.creer_bon_livraison.return_value = "BL-1"
    sales.creer_commande_client.return_value = "CDV-1"
    sales.valider_facture.return_value = {"facture_id": "FAC-1", "statut": "VALIDE"}
    sales.annuler_facture.return_value = {"facture_id": "FAC-1", "statut": "ANNULE"}
    sales.calculer_montants_facture.return_value = {
        "total_ht": 100., "total_remise": 0., "net_a_payer": 100.,
        "total_tva": 19., "timbre_fiscal": 0., "total_ttc": 119.,
    }

    core_package = types.ModuleType("core")
    core_package.__path__ = [str(Path(__file__).resolve().parents[1] / "core")]
    utils = types.ModuleType("core.utils")
    from datetime import datetime
    utils.get_local_now = MagicMock(return_value=datetime(2026, 10, 29, 23, 30))
    for key, val in {
        "streamlit": st,
        "config": types.ModuleType("config"),
        "config.roles": roles,
        "core": core_package,
        "core.db_service": db,
        "core.utils": utils,
        "modules": types.ModuleType("modules"),
        "modules.ventes": types.ModuleType("modules.ventes"),
        "modules.ventes.service": sales,
    }.items():
        monkeypatch.setitem(sys.modules, key, val)
    spec = importlib.util.spec_from_file_location("sales_views_tested", VIEW)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return types.SimpleNamespace(mod=mod, st=st, sales=sales, roles=roles, db=db, query=query, utils=utils)


def _draft():
    return {"client_id": "CLI-1", "date_echeance": "2026-11-01",
            "panier": [{"sku_id": "SKU-1", "quantite": 3, "prix_unitaire": 10, "remise": 0}],
            "remise_globale": 0, "paiement_especes": False,
            "is_avoir": False, "facture_origine_id": ""}


def _ship():
    return {"commande_vente_id": "CDV-1", "transporteur": "T", "zone": "Z",
            "items_livraison": [{"sku_id": "SKU-1", "quantite_livree": 2}]}


def _factures():
    return pd.DataFrame([
        {"facture_id": "FAC-1", "client_id": "CLI-1", "statut": "BROUILLON", "type_facture": "FactureClient"},
        {"facture_id": "FAC-2", "client_id": "CLI-1", "statut": "VALIDE", "type_facture": "FactureClient"},
        {"facture_id": "AV-1", "client_id": "CLI-1", "statut": "VALIDE", "type_facture": "FactureAvoir"},
        {"facture_id": "FAC-3", "client_id": "CLI-2", "statut": "VALIDE", "type_facture": "FactureClient"},
    ])


@pytest.mark.parametrize("authenticated,user", [
    (False, {"user_id": "USR-1"}), (True, None), (True, {}),
    (True, {"user_id": 1}), (True, {"user_id": " "}),
])
def test_invalid_sessions_deny_before_data_access(ui, authenticated, user):
    ui.st.session_state = {"authenticated": authenticated, "user": user}
    ui.mod.show_ventes_page()
    ui.sales.get_factures.assert_not_called()
    ui.db.fetch_data_paginated.assert_not_called()


def test_inactive_user_denied(ui):
    ui.query.execute.return_value = types.SimpleNamespace(
        data=[{"user_id": "USR-1", "role": "VENDEUR", "actif": "NON"}])
    ui.mod.show_ventes_page()
    ui.sales.get_factures.assert_not_called()


def test_unknown_or_multiple_users_denied(ui):
    for data in ([], [{"user_id": "USR-2", "role": "VENDEUR", "actif": "OUI"}],
                 [{"user_id": "USR-1", "role": "VENDEUR", "actif": "OUI"}] * 2):
        ui.query.execute.return_value = types.SimpleNamespace(data=data)
        ui.mod.show_ventes_page()
        ui.sales.get_factures.assert_not_called()


def test_permission_is_fresh_from_database(ui):
    ui.query.execute.return_value = types.SimpleNamespace(
        data=[{"user_id": "USR-1", "role": "LECTEUR", "actif": "OUI"}])
    ui.mod.show_ventes_page()
    assert ui.roles.has_permission.call_args_list[0].args == ("LECTEUR", "Ventes", "lecture")


def test_no_read_permission_denies_data_access(ui):
    ui.roles.has_permission.return_value = False
    ui.mod.show_ventes_page()
    ui.sales.get_factures.assert_not_called()


def test_access_backend_failure_denies(ui):
    ui.query.execute.side_effect = RuntimeError("db")
    ui.mod.show_ventes_page()
    ui.sales.get_factures.assert_not_called()


def test_read_only_view_never_offers_mutation(ui):
    ui.roles.has_permission.side_effect = [True, False]
    ui.mod.show_ventes_page()
    for f in (ui.sales.create_facture_brouillon, ui.sales.valider_facture,
              ui.sales.annuler_facture, ui.sales.creer_bon_livraison):
        f.assert_not_called()
    ui.roles.has_permission.side_effect = [True, False]
    assert ui.mod._sale_access() == ("USR-1", False)


@pytest.mark.parametrize("value", ["-1", "NaN", "Infinity", "-Infinity", True, "1e20", "abc", None])
def test_invalid_quantities_rejected(ui, value):
    with pytest.raises(ValueError):
        ui.mod._decimal(value, "Quantité", positive=True)


def test_zero_not_allowed_for_ship(ui):
    with pytest.raises(ValueError):
        ui.mod._decimal(0, "Quantité", positive=True)


@pytest.mark.parametrize("kind,service,expected", [
    ("draft", "create_facture_brouillon", "FAC-1"),
    ("validate", "valider_facture", "FAC-1"),
    ("cancel", "annuler_facture", "FAC-1"),
    ("ship", "creer_bon_livraison", "BL-1"),
])
def test_each_operation_confirmed(ui, kind, service, expected):
    payload = _draft() if kind == "draft" else _ship() if kind == "ship" else {"facture_id": "FAC-1"}
    ui.mod._start_operation(kind, "USR-1", payload)
    key = ui.mod._operation_key(kind, "USR-1")
    assert ui.st.session_state[key]["status"] == "confirmed"
    assert ui.st.session_state[key]["document_id"] == expected
    assert ui.st.session_state[key]["operation_id"].startswith("SALE-UI-")
    getattr(ui.sales, service).assert_called_once()
    assert getattr(ui.sales, service).call_args.kwargs["operation_id"] == ui.st.session_state[key]["operation_id"]


@pytest.mark.parametrize("kind,service", [
    ("draft", "create_facture_brouillon"),
    ("validate", "valider_facture"),
    ("cancel", "annuler_facture"),
    ("ship", "creer_bon_livraison"),
])
def test_retry_after_unknown_commit_uses_same_id_and_payload(ui, kind, service):
    payload = _draft() if kind == "draft" else _ship() if kind == "ship" else {"facture_id": "FAC-1"}
    fn = getattr(ui.sales, service)
    original = fn.return_value
    fn.side_effect = RuntimeError("network timeout")
    ui.mod._start_operation(kind, "USR-1", payload)
    key = ui.mod._operation_key(kind, "USR-1")
    record = ui.st.session_state[key]
    frozen = deepcopy(record["payload"])
    opid = record["operation_id"]
    assert record["status"] == "uncertain"
    # Changes to original mutable payload must have no effect.
    payload.clear()
    fn.side_effect = None
    fn.return_value = original
    ui.mod._execute_operation(kind, "USR-1")
    assert ui.st.session_state[key]["status"] == "confirmed"
    assert record["payload"] == frozen
    assert len(fn.call_args_list) == 2
    assert all(c.kwargs["operation_id"] == opid for c in fn.call_args_list)
    assert all({k: v for k, v in c.kwargs.items() if k != "operation_id"} == frozen
               for c in fn.call_args_list)


def test_second_document_blocked_while_uncertain(ui):
    ui.sales.create_facture_brouillon.side_effect = RuntimeError("timeout")
    ui.mod._start_operation("draft", "USR-1", _draft())
    ui.mod._start_operation("draft", "USR-1", _draft())
    assert ui.sales.create_facture_brouillon.call_count == 1


def test_confirmed_result_not_reexecuted(ui):
    ui.mod._start_operation("ship", "USR-1", _ship())
    ui.mod._execute_operation("ship", "USR-1")
    ui.sales.creer_bon_livraison.assert_called_once()


def test_invalid_response_not_a_success(ui):
    ui.sales.valider_facture.return_value = {"statut": "VALIDE", "facture_id": "BAD"}
    ui.mod._start_operation("validate", "USR-1", {"facture_id": "FAC-1"})
    assert ui.st.session_state[ui.mod._operation_key("validate", "USR-1")]["status"] == "uncertain"


def test_local_error_clears_pending_for_correctable_input(ui):
    ui.sales.create_facture_brouillon.side_effect = ValueError("bad")
    ui.mod._start_operation("draft", "USR-1", _draft())
    assert ui.mod._operation_key("draft", "USR-1") not in ui.st.session_state


def test_draft_clears_cart_only_on_confirmation(ui):
    cart_key = ui.mod._cart_key("USR-1")
    ui.st.session_state[cart_key] = [1]
    ui.sales.create_facture_brouillon.side_effect = RuntimeError("timeout")
    ui.mod._start_operation("draft", "USR-1", _draft())
    assert ui.st.session_state[cart_key] == [1]
    ui.sales.create_facture_brouillon.side_effect = None
    ui.sales.create_facture_brouillon.return_value = "FAC-1"
    ui.mod._execute_operation("draft", "USR-1")
    assert ui.st.session_state[cart_key] == []


def test_user_keys_isolated(ui):
    assert ui.mod._cart_key("USR-A") != ui.mod._cart_key("USR-B")
    assert ui.mod._operation_key("ship", "USR-A") != ui.mod._operation_key("ship", "USR-B")


def test_pending_tampering_blocks_retry(ui):
    key = ui.mod._operation_key("ship", "USR-1")
    ui.st.session_state[key] = {"status": "uncertain", "operation_id": "malformed", "payload": _ship()}
    assert ui.mod._operation_panel("ship", "USR-1") is True
    ui.sales.creer_bon_livraison.assert_not_called()


def test_pending_retry_on_button(ui):
    key = ui.mod._operation_key("ship", "USR-1")
    ui.st.session_state[key] = {"status": "uncertain", "operation_id": "SALE-UI-test", "payload": _ship()}
    ui.st.button.side_effect = lambda label, **kw: label.startswith("Réessayer")
    assert ui.mod._operation_panel("ship", "USR-1") is True
    ui.sales.creer_bon_livraison.assert_called_once()
    assert ui.sales.creer_bon_livraison.call_args.kwargs["operation_id"] == "SALE-UI-test"


def test_origin_filter_only_same_client_validated_invoice(ui):
    assert ui.mod._valid_origins(_factures(), "CLI-1") == ["FAC-2"]
    assert ui.mod._valid_origins(_factures(), "CLI-2") == ["FAC-3"]


def test_empty_origin_returns_empty(ui):
    assert ui.mod._valid_origins(pd.DataFrame(), "CLI-1") == []


def test_origin_requires_all_columns(ui):
    with pytest.raises(ValueError):
        ui.mod._valid_origins(pd.DataFrame([{"facture_id": "FAC-1"}]), "CLI-1")


def _order_lines():
    return pd.DataFrame([
        {"commande_vente_id": "CDV-1", "sku_id": "SKU-1", "quantite": 10},
        {"commande_vente_id": "CDV-1", "sku_id": "SKU-1", "quantite": 5},
        {"commande_vente_id": "CDV-1", "sku_id": "SKU-2", "quantite": 4},
        {"commande_vente_id": "CDV-2", "sku_id": "SKU-1", "quantite": 7},
    ])


def _bls():
    return pd.DataFrame([
        {"bl_id": "BL-1", "commande_vente_id": "CDV-1", "statut": "EXPEDIE"},
        {"bl_id": "BL-2", "commande_vente_id": "CDV-1", "statut": "ANNULE"},
        {"bl_id": "BL-3", "commande_vente_id": "CDV-2", "statut": "EXPEDIE"},
    ])


def _bl_lines():
    return pd.DataFrame([
        {"bl_id": "BL-1", "sku_id": "SKU-1", "quantite_livree": 2},
        {"bl_id": "BL-1", "sku_id": "SKU-1", "quantite_livree": 3},
        {"bl_id": "BL-1", "sku_id": "SKU-2", "quantite_livree": 1},
        {"bl_id": "BL-2", "sku_id": "SKU-1", "quantite_livree": 8},
        {"bl_id": "BL-3", "sku_id": "SKU-1", "quantite_livree": 1},
    ])


def test_remaining_sums_previous_valid_shipped_batches(ui):
    result = ui.mod._remaining_for_order("CDV-1", _order_lines(), _bls(), _bl_lines())
    assert result == {"SKU-1": Decimal("10"), "SKU-2": Decimal("3")}


def test_other_order_does_not_count(ui):
    assert ui.mod._remaining_for_order("CDV-2", _order_lines(), _bls(), _bl_lines()) == {"SKU-1": Decimal(6)}


def test_zero_shipments_returns_full_order(ui):
    result = ui.mod._remaining_for_order("CDV-1", _order_lines(), pd.DataFrame(), pd.DataFrame())
    assert result == {"SKU-1": Decimal("15"), "SKU-2": Decimal("4")}


def test_over_shipped_blocked(ui):
    rows = pd.DataFrame([{"bl_id": "BL-1", "sku_id": "SKU-1", "quantite_livree": 22}])
    with pytest.raises(ValueError, match="sur-livrée"):
        ui.mod._remaining_for_order("CDV-1", _order_lines(), _bls(), rows)


def test_unknown_sku_in_historical_bl_blocked(ui):
    rows = pd.DataFrame([{"bl_id": "BL-1", "sku_id": "OTHER", "quantite_livree": 2}])
    with pytest.raises(ValueError, match="incohérente"):
        ui.mod._remaining_for_order("CDV-1", _order_lines(), _bls(), rows)


@pytest.mark.parametrize("qty", [-1, "NaN", "Infinity", 0])
def test_bad_historical_quantity_blocked(ui, qty):
    rows = pd.DataFrame([{"bl_id": "BL-1", "sku_id": "SKU-1", "quantite_livree": qty}])
    with pytest.raises(ValueError):
        ui.mod._remaining_for_order("CDV-1", _order_lines(), _bls(), rows)


def test_absent_order_lines_blocked(ui):
    with pytest.raises(ValueError):
        ui.mod._remaining_for_order("FAC-1", _order_lines(), _bls(), _bl_lines())


def test_draft_not_automatically_shipped_by_invoice_id(ui):
    ui.db.fetch_data_paginated.side_effect = lambda table, **kwargs: (
        [{"commande_vente_id": "CDV-1", "statut": "EN_ATTENTE"}]
        if table == "commandes_ventes" else []
    )
    ui.mod._ship_tab("USR-1", True)
    ui.sales.creer_bon_livraison.assert_not_called()
    ui.st.error.assert_called()


def test_ship_tab_no_order_prevents_ship(ui):
    ui.db.fetch_data_paginated.return_value = []
    ui.mod._ship_tab("USR-1", True)
    ui.sales.creer_bon_livraison.assert_not_called()


def test_cancel_only_brouillons(ui):
    ui.st.button.side_effect = lambda label, **kw: label == "Annuler ce brouillon"
    ui.mod._workflow_tab("USR-1", True, _factures())
    ui.sales.annuler_facture.assert_called_once()
    assert ui.sales.annuler_facture.call_args.kwargs["facture_id"] == "FAC-1"


def test_validated_invoice_not_listed_for_cancel(ui):
    df = _factures()
    df = df[df["statut"] == "VALIDE"]
    ui.mod._workflow_tab("USR-1", True, df)
    ui.sales.annuler_facture.assert_not_called()


def test_doc_generation_contains_no_fictitious_identity(ui):
    content = VIEW.read_text(encoding="utf-8")
    for forbidden in ("MON ENTREPRISE", "123 Zone Industrielle", "0555 00 00 00"):
        assert forbidden not in content


def test_no_direct_supabase_mutations_from_view(ui):
    content = VIEW.read_text(encoding="utf-8")
    assert ".rpc(" not in content
    assert "enregistrer_sortie_pf" not in content
    assert "enregistrer_entree_pf" not in content
    assert "auto_create_of_from_vente" not in content


def test_no_manual_lot_selection(ui):
    content = VIEW.read_text(encoding="utf-8")
    assert 'selectbox("Lot' not in content
    assert '"lot_id": "DEFAUT"' not in content


def test_schema_type_errors_are_fail_closed(ui):
    with pytest.raises(ValueError):
        ui.mod._remaining_for_order("CDV-1", pd.DataFrame([{"foo": 4}]), pd.DataFrame(), pd.DataFrame())


def test_no_shipping_while_read_only(ui):
    ui.mod._ship_tab("USR-1", False)
    ui.db.fetch_data_paginated.assert_not_called()
    ui.sales.creer_bon_livraison.assert_not_called()


def test_no_draft_creation_while_read_only(ui):
    ui.mod._draft_tab("USR-1", False, pd.DataFrame())
    ui.db.fetch_data_paginated.assert_not_called()
    ui.sales.create_facture_brouillon.assert_not_called()


def _configure_ship_ui(ui, *, shipped=0, stock=6):
    def read(table, **kwargs):
        tables = {
            "commandes_ventes": [{"commande_vente_id": "CDV-1", "statut": "EN_ATTENTE"}],
            "lignes_commande_ventes": [
                {"commande_vente_id": "CDV-1", "sku_id": "SKU-1", "quantite": 10}],
            "bons_livraison": [{"bl_id": "BL-1", "commande_vente_id": "CDV-1", "statut": "EXPEDIE"}]
            if shipped else [],
            "lignes_bons_livraison": [
                {"bl_id": "BL-1", "sku_id": "SKU-1", "quantite_livree": shipped}]
            if shipped else [],
            "stock_actuel_pf": [{"sku_id": "SKU-1", "quantite_disponible": stock}],
        }
        return tables[table]
    ui.db.fetch_data_paginated.side_effect = read


def test_ship_form_passes_real_order_and_no_manual_lot(ui):
    _configure_ship_ui(ui, shipped=3, stock=6)
    ui.st.number_input.return_value = 2
    ui.st.form_submit_button.return_value = True
    ui.mod._ship_tab("USR-1", True)
    ui.sales.creer_bon_livraison.assert_called_once()
    payload = ui.sales.creer_bon_livraison.call_args.kwargs
    assert payload["commande_vente_id"] == "CDV-1"
    assert payload["items_livraison"] == [{"sku_id": "SKU-1", "quantite_livree": 2.0}]
    assert "lot_id" not in payload["items_livraison"][0]
    assert payload["operation_id"].startswith("SALE-UI-")


def test_ship_quantity_cap_by_stock_and_remaining(ui):
    _configure_ship_ui(ui, shipped=8, stock=4)
    ui.mod._ship_tab("USR-1", True)
    assert ui.st.number_input.call_args.kwargs["max_value"] == 2
    _configure_ship_ui(ui, shipped=1, stock=3)
    ui.mod._ship_tab("USR-1", True)
    assert ui.st.number_input.call_args.kwargs["max_value"] == 3


def test_ship_form_refuses_zero_lines_even_on_click(ui):
    _configure_ship_ui(ui, stock=8)
    ui.st.number_input.return_value = 0.0
    ui.st.form_submit_button.return_value = True
    ui.mod._ship_tab("USR-1", True)
    ui.sales.creer_bon_livraison.assert_not_called()
    ui.st.error.assert_called()


def test_read_pagination_failure_blocks_screen(ui):
    ui.db.fetch_data_paginated.side_effect = RuntimeError("too many rows")
    ui.mod.show_ventes_page()
    ui.st.error.assert_called()
    ui.sales.creer_bon_livraison.assert_not_called()


def _order_test_tables():
    return {
        "commandes_ventes": pd.DataFrame(),
        "clients": pd.DataFrame([{"client_id": "CLI-0007", "nom": "EURL Lounes", "actif": "OUI"}]),
        "sku_conditionnement": pd.DataFrame([
            {"sku_id": "SKU-001", "actif": "OUI", "prix_vente_defaut": 1250.0},
            {"sku_id": "SKU-007", "actif": "OUI", "prix_vente_defaut": 1200.0},
        ]),
    }


def _order_test_payload():
    return {
        "client_id": "CLI-0007",
        "date_commande": "2026-10-24",
        "lignes": [{"sku_id": "SKU-001", "quantite": 1, "prix_unitaire": "1250.00"}],
    }


def test_order_tab_readonly_no_creation(ui):
    ui.mod._read_required = MagicMock(return_value=pd.DataFrame())
    ui.mod._order_tab("USR-1", False)
    ui.mod._read_required.assert_called_once_with("commandes_ventes")
    ui.st.form.assert_not_called()


def test_order_tab_cart_routes_to_operation_without_direct_write(ui):
    tables = _order_test_tables()
    ui.mod._read_required = MagicMock(side_effect=lambda table: tables[table])
    ui.st.number_input.side_effect = (
        lambda label, **kwargs: 1 if "Quantit" in label else 1250.0
    )
    ui.st.form_submit_button.side_effect = lambda label, **kwargs: label == "Ajouter au panier"
    ui.st.button.side_effect = lambda label, **kwargs: label == "Enregistrer la commande"
    ui.mod._start_operation = MagicMock()

    ui.mod._order_tab("USR-1", True)

    ui.mod._start_operation.assert_called_once()
    kind, user, payload = ui.mod._start_operation.call_args.args
    assert kind == "order"
    assert user == "USR-1"
    assert payload["client_id"] == "CLI-0007"
    assert payload["lignes"] == [
        {"sku_id": "SKU-001", "quantite": 1, "prix_unitaire": "1250.00"}
    ]


def test_order_tab_blocks_unvalidated_sku(ui):
    tables = _order_test_tables()
    tables["sku_conditionnement"] = tables["sku_conditionnement"].query(
        "sku_id == 'SKU-007'"
    )
    ui.mod._read_required = MagicMock(side_effect=lambda table: tables[table])
    ui.mod._start_operation = MagicMock()

    ui.mod._order_tab("USR-1", True)

    ui.st.warning.assert_called()
    ui.mod._start_operation.assert_not_called()
    ui.st.form.assert_not_called()


def test_order_tab_pending_operation_blocks_second_form(ui):
    key = ui.mod._operation_key("order", "USR-1")
    ui.st.session_state[key] = {
        "status": "uncertain", "operation_id": "SALE-UI-test009",
        "payload": _order_test_payload(),
    }
    ui.mod._read_required = MagicMock()
    ui.mod._order_tab("USR-1", True)
    ui.mod._read_required.assert_not_called()
    ui.st.form.assert_not_called()


def test_order_click_twice_creates_only_one_operation(ui):
    ui.mod.creer_commande_client.return_value = "CDV-0001"
    payload = _order_test_payload()
    ui.mod._start_operation("order", "USR-1", payload)
    ui.mod._start_operation("order", "USR-1", payload)
    ui.mod.creer_commande_client.assert_called_once()
    key = ui.mod._operation_key("order", "USR-1")
    assert ui.st.session_state[key]["status"] == "confirmed"
    assert ui.st.session_state[key]["document_id"] == "CDV-0001"


def test_order_timeout_retry_keeps_operation_id(ui):
    ui.mod.creer_commande_client.side_effect = [RuntimeError("timeout"), "CDV-0001"]
    payload = _order_test_payload()
    ui.mod._start_operation("order", "USR-1", payload)
    key = ui.mod._operation_key("order", "USR-1")
    assert ui.st.session_state[key]["status"] == "uncertain"
    previous_id = ui.st.session_state[key]["operation_id"]

    ui.mod._execute_operation("order", "USR-1")

    assert ui.mod.creer_commande_client.call_count == 2
    assert all(
        call.kwargs["operation_id"] == previous_id
        for call in ui.mod.creer_commande_client.call_args_list
    )
    assert ui.st.session_state[key]["status"] == "confirmed"


def test_tva_ui_ne_lit_rien_sans_clic(ui):
    ui.mod._controle_tva_sku_tab("USR-1")
    ui.db.fetch_data_paginated.assert_not_called()
    ui.st.metric.assert_not_called()


def test_tva_ui_refuse_sans_permission(ui):
    ui.mod._sale_access = MagicMock(return_value=None)
    ui.st.button.return_value = True
    ui.mod._controle_tva_sku_tab("USR-1")
    ui.db.fetch_data_paginated.assert_not_called()
    ui.st.metric.assert_not_called()


def test_tva_ui_couverture_sans_classification(ui):
    ui.st.button.return_value = True
    ui.mod._sale_access = MagicMock(return_value=("USR-1", False))
    ui.db.fetch_data_paginated.return_value = [
        {"sku_id": "SKU-1", "pf_id": "PF-1", "actif": "OUI"}
    ]
    client = ui.db.get_supabase_client.return_value
    response = client.table.return_value.select.return_value.range.return_value
    response.execute.return_value = types.SimpleNamespace(data=[], count=0)
    ui.mod._controle_tva_sku_tab("USR-1")
    ui.st.metric.assert_any_call("SKU non classés", 1)
    ui.st.dataframe.assert_called_once()
    ui.sales.create_facture_brouillon.assert_not_called()
    ui.sales.valider_facture.assert_not_called()


def test_tva_ui_refuse_lecture_tronquee(ui):
    ui.st.button.return_value = True
    ui.mod._sale_access = MagicMock(return_value=("USR-1", False))
    ui.db.fetch_data_paginated.return_value = [{"sku_id": "SKU-1"}]
    client = ui.db.get_supabase_client.return_value
    response = client.table.return_value.select.return_value.range.return_value
    response.execute.return_value = types.SimpleNamespace(data=[], count=1)
    ui.mod._controle_tva_sku_tab("USR-1")
    ui.st.metric.assert_not_called()
    ui.st.dataframe.assert_not_called()
    ui.st.error.assert_called()


def test_tva_ui_export_registre_non_homologue_apres_lecture_autorisee(ui):
    ui.st.button.return_value = True
    ui.mod._sale_access = MagicMock(return_value=("USR-1", False))
    ui.db.fetch_data_paginated.return_value = [{
        "sku_id": "SKU-001", "pf_id": "PF-001",
        "format": "Sac 25kg", "unite_vente": "SAC", "actif": "OUI",
    }]
    client = ui.db.get_supabase_client.return_value
    response = client.table.return_value.select.return_value.range.return_value
    response.execute.return_value = types.SimpleNamespace(data=[], count=0)

    ui.mod._controle_tva_sku_tab("USR-1")

    ui.st.download_button.assert_called_once()
    data = ui.st.download_button.call_args.kwargs["data"]
    assert "SKU-001" in data
    assert "À qualifier" in data
    assert "Document de travail non homologué" in data
    ui.sales.create_facture_brouillon.assert_not_called()


def test_tva_ui_n_exporte_pas_si_sku_incomplet(ui):
    ui.st.button.return_value = True
    ui.mod._sale_access = MagicMock(return_value=("USR-1", False))
    ui.db.fetch_data_paginated.return_value = [{
        "sku_id": "SKU-001", "pf_id": "PF-001", "actif": "OUI",
    }]
    client = ui.db.get_supabase_client.return_value
    response = client.table.return_value.select.return_value.range.return_value
    response.execute.return_value = types.SimpleNamespace(data=[], count=0)

    ui.mod._controle_tva_sku_tab("USR-1")

    ui.st.download_button.assert_not_called()
    ui.st.info.assert_called()


def test_draft_view_affiche_avertissement_fiscal_historique(ui):
    ui.mod._draft_tab("USR-1", False, pd.DataFrame())
    messages = [call.args[0] for call in ui.st.warning.call_args_list]
    assert any("TVA uniforme" in message for message in messages)
    assert any("facturation réglementaire homologuée" in message for message in messages)
    ui.sales.create_facture_brouillon.assert_not_called()


def test_tva_ui_compte_et_exporte_uniquement_sku_actifs(ui):
    ui.st.button.return_value = True
    ui.mod._sale_access = MagicMock(return_value=("USR-1", False))
    ui.db.fetch_data_paginated.return_value = [
        {"sku_id": "SKU-A", "pf_id": "PF-A", "format": "Sac 25kg",
         "unite_vente": "SAC", "actif": "OUI"},
        {"sku_id": "SKU-I", "pf_id": "PF-I", "format": "Fut 200L",
         "unite_vente": "FUT", "actif": "NON"},
    ]
    client = ui.db.get_supabase_client.return_value
    response = client.table.return_value.select.return_value.range.return_value
    response.execute.return_value = types.SimpleNamespace(data=[], count=0)

    ui.mod._controle_tva_sku_tab("USR-1")

    ui.st.metric.assert_any_call("SKU contrôlés", 1)
    ui.st.metric.assert_any_call("SKU non classés", 1)
    ui.st.download_button.assert_called_once()
    exported = ui.st.download_button.call_args.kwargs["data"]
    assert "SKU-A" in exported
    assert "SKU-I" not in exported
    ui.sales.create_facture_brouillon.assert_not_called()


def test_tva_ui_utilise_date_locale_erp_et_non_horloge_serveur(ui):
    ui.st.button.return_value = True
    ui.mod._sale_access = MagicMock(return_value=("USR-1", False))
    ui.db.fetch_data_paginated.return_value = [{
        "sku_id": "SKU-001", "pf_id": "PF-001",
        "format": "Sac 25kg", "unite_vente": "SAC", "actif": "OUI",
    }]
    client = ui.db.get_supabase_client.return_value
    response = client.table.return_value.select.return_value.range.return_value
    response.execute.return_value = types.SimpleNamespace(data=[], count=0)
    from core import couverture_tva_sku
    from unittest.mock import patch
    with patch.object(couverture_tva_sku, "verifier_couverture_tva",
                      wraps=couverture_tva_sku.verifier_couverture_tva) as spy:
        ui.mod._controle_tva_sku_tab("USR-1")
        assert spy.call_args.args[2] == "2026-10-29"
        assert spy.call_args.kwargs["uniquement_actifs"] is True
        ui.utils.get_local_now.assert_called_once()


def test_reperage_version_interface_apres_autorisation(ui):
    for nom in ("_draft_tab", "_order_tab", "_ship_tab", "_workflow_tab",
                "_controle_tva_sku_tab"):
        setattr(ui.mod, nom, MagicMock())
    ui.mod.show_ventes_page()
    ui.st.caption.assert_any_call(
        "Version interface Ventes : SOF-ERP-20261029-TVA-ASOF-01"
    )


def test_reperage_version_non_affiche_sans_permission(ui):
    ui.roles.has_permission.return_value = False
    ui.mod.show_ventes_page()
    ui.st.caption.assert_not_called()


def test_exoneration_client_signalee_bloque_brouillon_historique(ui):
    ui.mod._operation_panel = MagicMock(return_value=False)
    ui.mod._start_operation = MagicMock()
    donnees = {
        "clients": pd.DataFrame([{"client_id": "CLI-1", "nom": "TEST", "actif": "OUI"}]),
        "sku_conditionnement": pd.DataFrame([
            {"sku_id": "SKU-A", "pf_id": "PF-A", "format": "Sac 25kg", "actif": "OUI"}
        ]),
        "produits": pd.DataFrame([{"pf_id": "PF-A", "nom": "TEST", "actif": "OUI"}]),
    }
    ui.mod._read_required = MagicMock(side_effect=lambda table: donnees[table])
    ui.st.checkbox.return_value = True

    ui.mod._draft_tab("USR-1", True, pd.DataFrame())

    ui.st.checkbox.assert_any_call(
        "Client avec attestation d'exonération TVA (facturation dédiée non activée)",
        key="vente_exoneration_signalee_CLI-1",
    )
    assert any(
        "Facture client exonéré bloquée" in call.args[0]
        for call in ui.st.warning.call_args_list
    )
    ui.mod._start_operation.assert_not_called()
    ui.sales.create_facture_brouillon.assert_not_called()
    ui.st.number_input.assert_not_called()
