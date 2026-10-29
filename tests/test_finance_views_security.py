"""Finance UI : permissions, comptabilité, reprises anti-doublons (sans réseau)."""
import importlib.util
import sys
import types
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

VIEW = Path(__file__).resolve().parents[1] / "modules" / "finance" / "views.py"


@pytest.fixture
def ui(monkeypatch):
    st = MagicMock()
    st.session_state = {"authenticated": True, "user": {"user_id": "USR-1", "role": "FINANCIER"}}
    st.tabs.side_effect = lambda labels: [MagicMock() for _ in labels]
    st.columns.side_effect = lambda widths: [MagicMock() for _ in range(widths if isinstance(widths, int) else len(widths))]
    st.button.return_value = False
    st.form_submit_button.return_value = False
    st.radio.side_effect = lambda label, options, **kw: options[0]
    st.selectbox.side_effect = lambda label, options, **kw: options[0]
    st.date_input.return_value = "2026-10-21"
    st.number_input.return_value = 100.00
    st.text_input.return_value = "REF"

    client = MagicMock()
    query = client.table.return_value.select.return_value.eq.return_value.limit.return_value
    query.execute.return_value = types.SimpleNamespace(data=[
        {"user_id": "USR-1", "role": "FINANCIER", "actif": "OUI"},
    ])
    db = types.ModuleType("core.db_service")
    db.get_supabase_client = MagicMock(return_value=client)
    db.fetch_data_paginated = MagicMock(return_value=[])
    roles = types.ModuleType("config.roles")
    roles.has_permission = MagicMock(return_value=True)

    listes = types.ModuleType("core.listes_service")
    listes.get_liste = MagicMock(return_value=[])
    listes.liste_to_dict = MagicMock(return_value={})

    finance = types.ModuleType("modules.finance.service")
    for name in ("creer_compte", "enregistrer_reglement", "enregistrer_lettrage",
                 "creer_accuse_encaissement",
                 "get_comptes", "get_reglements", "get_lettrages", "get_ecritures_comptables"):
        setattr(finance, name, MagicMock())
    finance.creer_compte.return_value = "CPT-1"
    finance.enregistrer_reglement.return_value = "REG-1"
    finance.enregistrer_lettrage.return_value = "LET-1"
    finance.creer_accuse_encaissement.return_value = "RINT-1"
    finance.get_comptes.return_value = pd.DataFrame()
    finance.get_reglements.return_value = pd.DataFrame()
    finance.get_lettrages.return_value = pd.DataFrame()
    finance.get_ecritures_comptables.return_value = pd.DataFrame()
    for key, value in {
        "streamlit": st, "config": types.ModuleType("config"),
        "config.roles": roles, "core": types.ModuleType("core"),
        "core.db_service": db, "core.listes_service": listes,
        "modules": types.ModuleType("modules"),
        "modules.finance": types.ModuleType("modules.finance"),
        "modules.finance.service": finance,
    }.items():
        monkeypatch.setitem(sys.modules, key, value)
    spec = importlib.util.spec_from_file_location("finance_views_tested", VIEW)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return types.SimpleNamespace(mod=mod, st=st, roles=roles,
                                 finance=finance, db=db, query=query)


def _account():
    return {"nom_compte": "Banque", "type_compte": "Banque",
            "numero_compte": "512", "solde_initial": 50.0}


def _payment():
    return {"date_reglement": "2026-10-21", "type_flux": "ENCAISSEMENT",
            "partenaire_id": "CLI-1", "compte_id": "CPT-CASH",
            "mode_paiement": "VIREMENT", "reference_trace": "WIRE-1",
            "montant_total": 100.0, "contrepartie_compte_id": "CPT-411"}


def _allocation():
    return {"reglement_id": "REG-1", "document_id": "FAC-1",
            "type_document": "FactureClient", "montant_applique": 50.0}


def _accounts():
    return pd.DataFrame([
        {"compte_id": "CPT-CASH", "nom_compte": "Banque principale", "type_compte": "Banque", "statut": "OUI"},
        {"compte_id": "CPT-CAISSE", "nom_compte": "Caisse", "type_compte": "Caisse", "statut": "OUI"},
        {"compte_id": "CPT-411", "nom_compte": "Clients", "type_compte": "Tiers client", "statut": "OUI"},
        {"compte_id": "CPT-401", "nom_compte": "Fournisseurs", "type_compte": "Tiers fournisseur", "statut": "OUI"},
        {"compte_id": "CPT-OFF", "nom_compte": "Inactive", "type_compte": "Banque", "statut": "NON"},
    ])


def _payments():
    return pd.DataFrame([
        {"reglement_id": "REG-1", "type_flux": "ENCAISSEMENT", "partenaire_id": "CLI-1",
         "montant_total": 100, "montant_alloue": 50, "statut": "VALIDE"},
        {"reglement_id": "REG-2", "type_flux": "DECAISSEMENT", "partenaire_id": "FRN-1",
         "montant_total": 200, "montant_alloue": 0, "statut": "VALIDE"},
        {"reglement_id": "REG-3", "type_flux": "ENCAISSEMENT", "partenaire_id": "CLI-2",
         "montant_total": 10, "montant_alloue": 10, "statut": "VALIDE"},
        {"reglement_id": "REG-4", "type_flux": "ENCAISSEMENT", "partenaire_id": "CLI-1",
         "montant_total": 20, "montant_alloue": 0, "statut": "ANNULE"},
    ])


def _invoices():
    return pd.DataFrame([
        {"facture_id": "FAC-1", "client_id": "CLI-1", "statut": "VALIDE",
         "type_facture": "FactureClient", "montant_ttc": 100, "montant_paye": 25},
        {"facture_id": "FAC-2", "client_id": "CLI-2", "statut": "VALIDE",
         "type_facture": "FactureClient", "montant_ttc": 50, "montant_paye": 0},
        {"facture_id": "AV-1", "client_id": "CLI-1", "statut": "VALIDE",
         "type_facture": "FactureAvoir", "montant_ttc": -20, "montant_paye": 0},
        {"facture_id": "FAC-3", "client_id": "CLI-1", "statut": "BROUILLON",
         "type_facture": "FactureClient", "montant_ttc": 200, "montant_paye": 0},
    ])


def _supplier_invoices():
    return pd.DataFrame([
        {"facture_fournisseur_id": "FF-1", "fournisseur_id": "FRN-1",
         "montant_ttc": 300, "statut_paiement": "PARTIELLE"},
        {"facture_fournisseur_id": "FF-2", "fournisseur_id": "FRN-2",
         "montant_ttc": 25, "statut_paiement": "NON_PAYEE"},
        {"facture_fournisseur_id": "FF-3", "fournisseur_id": "FRN-1",
         "montant_ttc": 100, "statut_paiement": "REJETE"},
    ])


@pytest.mark.parametrize("authenticated,user", [
    (False, {"user_id": "USR-1"}), (True, None), (True, {}),
    (True, {"user_id": 1}), (True, {"user_id": " "}),
])
def test_access_denied_before_finance_read(ui, authenticated, user):
    ui.st.session_state = {"authenticated": authenticated, "user": user}
    ui.mod.show_finance_page()
    ui.db.fetch_data_paginated.assert_not_called()
    ui.db.fetch_data_paginated.assert_not_called()


@pytest.mark.parametrize("records", [
    [], [{"user_id": "USR-2", "role": "FINANCIER", "actif": "OUI"}],
    [{"user_id": "USR-1", "role": "FINANCIER", "actif": "NON"}],
    [{"user_id": "USR-1", "role": "FINANCIER", "actif": "OUI"}] * 2,
])
def test_database_account_must_be_unique_active_matching(ui, records):
    ui.query.execute.return_value = types.SimpleNamespace(data=records)
    ui.mod.show_finance_page()
    ui.db.fetch_data_paginated.assert_not_called()


def test_backend_access_errors_denied(ui):
    ui.query.execute.side_effect = RuntimeError("db")
    assert ui.mod._finance_access() is None
    ui.mod.show_finance_page()
    ui.db.fetch_data_paginated.assert_not_called()


def test_role_read_denied(ui):
    ui.roles.has_permission.return_value = False
    ui.mod.show_finance_page()
    ui.db.fetch_data_paginated.assert_not_called()


def test_role_checked_from_database_not_session(ui):
    ui.query.execute.return_value = types.SimpleNamespace(data=[
        {"user_id": "USR-1", "role": "LECTEUR", "actif": "OUI"}])
    assert ui.mod._finance_access() == ("USR-1", True)
    assert ui.roles.has_permission.call_args_list[0].args == ("LECTEUR", "Finance", "lecture")


def test_read_only_ui_does_not_mutate(ui):
    ui.roles.has_permission.side_effect = [True, False]
    ui.mod.show_finance_page()
    for fn in (ui.finance.creer_compte, ui.finance.enregistrer_reglement, ui.finance.enregistrer_lettrage):
        fn.assert_not_called()


def test_access_precedes_any_sensitive_read(ui):
    ui.roles.has_permission.return_value = False
    ui.mod.show_finance_page()
    ui.db.fetch_data_paginated.assert_not_called()
    ui.db.fetch_data_paginated.assert_not_called()


@pytest.mark.parametrize("kind,payload,name,result", [
    ("account", _account(), "creer_compte", "CPT-1"),
    ("payment", _payment(), "enregistrer_reglement", "REG-1"),
    ("allocate", _allocation(), "enregistrer_lettrage", "LET-1"),
])
def test_operation_confirmed(ui, kind, payload, name, result):
    ui.mod._start_operation(kind, "USR-1", payload)
    key = ui.mod._op_key(kind, "USR-1")
    record = ui.st.session_state[key]
    assert record["status"] == "confirmed"
    assert record["document_id"] == result
    assert record["operation_id"].startswith("FIN-UI-")
    getattr(ui.finance, name).assert_called_once()
    assert getattr(ui.finance, name).call_args.kwargs["operation_id"] == record["operation_id"]


@pytest.mark.parametrize("kind,payload,name", [
    ("account", _account(), "creer_compte"),
    ("payment", _payment(), "enregistrer_reglement"),
    ("allocate", _allocation(), "enregistrer_lettrage"),
])
def test_after_timeout_retry_same_operation_and_payload(ui, kind, payload, name):
    fn = getattr(ui.finance, name)
    result = fn.return_value
    fn.side_effect = RuntimeError("timeout after commit")
    ui.mod._start_operation(kind, "USR-1", payload)
    key = ui.mod._op_key(kind, "USR-1")
    record = ui.st.session_state[key]
    frozen = deepcopy(record["payload"])
    op_id = record["operation_id"]
    assert record["status"] == "uncertain"
    payload.clear()
    fn.side_effect = None
    fn.return_value = result
    ui.mod._execute_operation(kind, "USR-1")
    assert record["status"] == "confirmed"
    assert len(fn.call_args_list) == 2
    for call in fn.call_args_list:
        assert call.kwargs["operation_id"] == op_id
        assert {k: v for k, v in call.kwargs.items() if k != "operation_id"} == frozen


def test_duplicate_payment_blocked_while_uncertain(ui):
    ui.finance.enregistrer_reglement.side_effect = RuntimeError("timeout")
    ui.mod._start_operation("payment", "USR-1", _payment())
    ui.mod._start_operation("payment", "USR-1", _payment())
    ui.finance.enregistrer_reglement.assert_called_once()


def test_confirmed_not_reexecuted(ui):
    ui.mod._start_operation("payment", "USR-1", _payment())
    ui.mod._execute_operation("payment", "USR-1")
    ui.finance.enregistrer_reglement.assert_called_once()


def test_invalid_response_not_success(ui):
    ui.finance.enregistrer_reglement.return_value = None
    ui.mod._start_operation("payment", "USR-1", _payment())
    assert ui.st.session_state[ui.mod._op_key("payment", "USR-1")]["status"] == "uncertain"


def test_local_error_resets_pending(ui):
    ui.finance.enregistrer_reglement.side_effect = ValueError("counterparty missing")
    ui.mod._start_operation("payment", "USR-1", _payment())
    assert ui.mod._op_key("payment", "USR-1") not in ui.st.session_state


def test_pending_panel_tampered_fails_closed(ui):
    ui.st.session_state[ui.mod._op_key("payment", "USR-1")] = {
        "status": "uncertain", "operation_id": "bad", "payload": _payment()}
    assert ui.mod._operation_panel("payment", "USR-1") is True
    ui.finance.enregistrer_reglement.assert_not_called()


def test_pending_panel_retries_on_action(ui):
    ui.st.session_state[ui.mod._op_key("payment", "USR-1")] = {
        "status": "uncertain", "operation_id": "FIN-UI-original", "payload": _payment()}
    ui.st.button.side_effect = lambda label, **kw: label == "Réessayer la même opération"
    assert ui.mod._operation_panel("payment", "USR-1") is True
    assert ui.finance.enregistrer_reglement.call_args.kwargs["operation_id"] == "FIN-UI-original"


def test_pending_panel_confirmed_can_reset(ui):
    ui.mod._start_operation("payment", "USR-1", _payment())
    ui.st.button.side_effect = lambda label, **kw: label == "Préparer une nouvelle opération"
    ui.mod._operation_panel("payment", "USR-1")
    assert ui.mod._op_key("payment", "USR-1") not in ui.st.session_state


def test_user_operations_isolated(ui):
    assert ui.mod._op_key("payment", "USR-A") != ui.mod._op_key("payment", "USR-B")
    assert ui.mod._op_key("account", "USR-A") != ui.mod._op_key("payment", "USR-A")


@pytest.mark.parametrize("amount", ["NaN", "Infinity", "-Infinity", "abc", True, None, -1, 0, "1e15", 1.234])
def test_invalid_amounts_rejected(ui, amount):
    with pytest.raises(ValueError):
        ui.mod._money(amount, "Montant")


def test_zero_may_be_opening_balance(ui):
    assert ui.mod._money(0, "Solde initial", allow_zero=True) == Decimal(0)


def test_money_decimal_cents(ui):
    assert ui.mod._money("1.20", "Montant") == Decimal("1.20")


def test_account_types_filter(ui):
    df = _accounts()
    assert set(ui.mod._active_account_rows(df, ui.mod._TREASURY_TYPES)) == {"CPT-CASH", "CPT-CAISSE"}
    assert set(ui.mod._active_account_rows(df, ui.mod._COUNTER_TYPES["ENCAISSEMENT"])) == {"CPT-411"}
    assert set(ui.mod._active_account_rows(df, ui.mod._COUNTER_TYPES["DECAISSEMENT"])) == {"CPT-401"}


def test_account_types_missing_columns_fails_closed(ui):
    with pytest.raises(ValueError):
        ui.mod._active_account_rows(pd.DataFrame([{"compte_id": "a"}]), ui.mod._TREASURY_TYPES)


def test_open_payment_filters_status_flow_allocations(ui):
    opened = ui.mod._open_payments(_payments(), "ENCAISSEMENT")
    assert len(opened) == 1
    assert opened.iloc[0]["reglement_id"] == "REG-1"
    assert opened.iloc[0]["restant"] == Decimal("50")


def test_overallocated_payment_fails_closed(ui):
    df = _payments()
    df.loc[0, "montant_alloue"] = 101
    with pytest.raises(ValueError):
        ui.mod._open_payments(df, "ENCAISSEMENT")


def test_open_payment_requires_all_columns(ui):
    with pytest.raises(ValueError):
        ui.mod._open_payments(pd.DataFrame([{"reglement_id": "REG-1"}]), "ENCAISSEMENT")


def test_customer_invoices_only_valid_matching_client_no_credits(ui):
    eligible = ui.mod._open_invoices(_invoices(), "FactureClient", "CLI-1")
    assert eligible == [{"document_id": "FAC-1", "reste": Decimal("75")}]


def test_supplier_invoice_amount_uses_lettrage_not_status(ui):
    allocations = pd.DataFrame([
        {"type_document": "FactureFournisseur", "document_id": "FF-1", "montant_applique": 40},
        {"type_document": "FactureClient", "document_id": "FAC-1", "montant_applique": 90},
        {"type_document": "FactureFournisseur", "document_id": "FF-1", "montant_applique": 10},
    ])
    eligible = ui.mod._open_invoices(_supplier_invoices(), "FactureFournisseur", "FRN-1", allocations)
    assert eligible == [{"document_id": "FF-1", "reste": Decimal("250")}]


def test_supplier_overpaid_fails_closed(ui):
    allocations = pd.DataFrame([{"type_document": "FactureFournisseur", "document_id": "FF-1", "montant_applique": 301}])
    with pytest.raises(ValueError):
        ui.mod._open_invoices(_supplier_invoices(), "FactureFournisseur", "FRN-1", allocations)


def test_invoice_missing_columns_fails(ui):
    with pytest.raises(ValueError):
        ui.mod._open_invoices(pd.DataFrame([{"facture_id": "FA-1"}]), "FactureClient", "CLI-1")


def test_journal_imbalanced_warns(ui):
    df = pd.DataFrame([{"date_ecriture": "2026-10-21", "debit": 100, "credit": 0}])
    ui.mod._journal(df)
    ui.st.warning.assert_called()


def test_journal_balanced_does_not_claim_general_ledger(ui):
    df = pd.DataFrame([{"date_ecriture": "2026-10-21", "debit": 100, "credit": 100}])
    ui.mod._journal(df)
    assert "ne valide pas toute la comptabilité" in ui.st.info.call_args.args[0]


def test_payment_blocked_without_counterparty(ui):
    ui.mod._payment_tab("USR-1", True, pd.DataFrame([_accounts().iloc[0].to_dict()]))
    ui.finance.enregistrer_reglement.assert_not_called()


def test_payment_uses_distinct_counterparty(ui):
    ui.db.fetch_data_paginated.return_value = [{"client_id": "CLI-1", "nom": "Client"}]
    ui.st.form_submit_button.return_value = True
    ui.mod._payment_tab("USR-1", True, _accounts())
    ui.finance.enregistrer_reglement.assert_called_once()
    kw = ui.finance.enregistrer_reglement.call_args.kwargs
    assert kw["compte_id"] == "CPT-CASH"
    assert kw["contrepartie_compte_id"] == "CPT-411"
    assert kw["operation_id"].startswith("FIN-UI-")


def test_read_only_payment_no_service_call(ui):
    ui.mod._payment_tab("USR-1", False, _accounts())
    ui.finance.enregistrer_reglement.assert_not_called()


def test_allocation_only_same_client_and_valid(ui):
    ui.db.fetch_data_paginated.return_value = _invoices().to_dict(orient="records")
    ui.st.form_submit_button.return_value = True
    ui.st.number_input.return_value = 25.0
    ui.mod._allocation_tab("USR-1", True, _payments())
    ui.finance.enregistrer_lettrage.assert_called_once()
    kw = ui.finance.enregistrer_lettrage.call_args.kwargs
    assert kw["document_id"] == "FAC-1"
    assert kw["type_document"] == "FactureClient"
    assert kw["reglement_id"] == "REG-1"


def test_allocation_supplier_flow(ui):
    ui.st.radio.side_effect = None
    ui.st.radio.return_value = "FactureFournisseur"
    ui.db.fetch_data_paginated.side_effect = lambda name, **kw: (_supplier_invoices().to_dict(orient="records") if name == "factures_fournisseurs" else [])
    ui.st.form_submit_button.return_value = True
    ui.st.number_input.return_value = 25.0
    ui.mod._allocation_tab("USR-1", True, _payments())
    ui.finance.enregistrer_lettrage.assert_called_once()
    assert ui.finance.enregistrer_lettrage.call_args.kwargs["type_document"] == "FactureFournisseur"
    assert ui.finance.enregistrer_lettrage.call_args.kwargs["reglement_id"] == "REG-2"


def test_allocation_more_than_due_refused(ui):
    ui.db.fetch_data_paginated.return_value = _invoices().to_dict(orient="records")
    ui.st.number_input.return_value = 1000
    ui.st.form_submit_button.return_value = True
    ui.mod._allocation_tab("USR-1", True, _payments())
    ui.finance.enregistrer_lettrage.assert_not_called()


def test_no_rpc_direct_and_no_raw_update(ui):
    source = VIEW.read_text(encoding="utf-8")
    assert ".rpc(" not in source
    assert "update_hybrid" not in source
    assert "insert_hybrid" not in source


def test_all_page_reads_are_after_access(ui):
    ui.mod.show_finance_page()
    assert ui.db.fetch_data_paginated.call_count >= 3
    assert [c.args[0] for c in ui.db.fetch_data_paginated.call_args_list][:2] == ["comptes", "reglements"]


def test_failed_finance_loading_blocks(ui):
    ui.db.fetch_data_paginated.side_effect = RuntimeError("db")
    ui.mod.show_finance_page()
    assert ui.db.fetch_data_paginated.call_count == 1


def test_number_missing_duplicate_reference_not_sent(ui):
    ui.db.fetch_data_paginated.return_value = [{"client_id": "CLI-1", "nom": "Client"}]
    ui.st.form_submit_button.return_value = True
    ui.st.text_input.return_value = " "
    ui.mod._payment_tab("USR-1", True, _accounts())
    ui.finance.enregistrer_reglement.assert_not_called()


def test_payment_flow_customer_and_supplier_separate(ui):
    ui.db.fetch_data_paginated.side_effect = lambda name, **kw: (
        [{"fournisseur_id": "FRN-1", "nom": "Fourni"}] if name == "fournisseurs"
        else [{"client_id": "CLI-1", "nom": "Client"}]
    )
    ui.st.radio.side_effect = None
    ui.st.radio.return_value = "DECAISSEMENT"
    ui.st.form_submit_button.return_value = True
    ui.mod._payment_tab("USR-1", True, _accounts())
    kw = ui.finance.enregistrer_reglement.call_args.kwargs
    assert kw["partenaire_id"] == "FRN-1"
    assert kw["contrepartie_compte_id"] == "CPT-401"


def test_no_selection_without_partner(ui):
    ui.db.fetch_data_paginated.return_value = []
    ui.mod._payment_tab("USR-1", True, _accounts())
    ui.finance.enregistrer_reglement.assert_not_called()


def test_unique_operation_ids_differ_per_new_action(ui):
    ui.mod._start_operation("account", "USR-1", _account())
    key = ui.mod._op_key("account", "USR-1")
    first = ui.st.session_state[key]["operation_id"]
    del ui.st.session_state[key]
    ui.mod._start_operation("account", "USR-1", _account())
    second = ui.st.session_state[key]["operation_id"]
    assert first != second


def test_supplier_paid_status_hidden_despite_missing_ledger(ui):
    df = _supplier_invoices()
    df.loc[0, "statut_paiement"] = "PAYEE"
    assert ui.mod._open_invoices(df, "FactureFournisseur", "FRN-1", pd.DataFrame()) == []


def test_supplier_requires_allocation_history(ui):
    with pytest.raises(ValueError, match="obligatoire"):
        ui.mod._open_invoices(_supplier_invoices(), "FactureFournisseur", "FRN-1")


def test_paginated_reads_used_for_financial_totals(ui):
    ui.mod.show_finance_page()
    names = [c.args[0] for c in ui.db.fetch_data_paginated.call_args_list]
    assert "reglements" in names and "comptes" in names and "ecritures_comptables" in names
    for call in ui.db.fetch_data_paginated.call_args_list:
        assert call.kwargs.get("max_rows") == 10000


def test_supply_lettrage_history_paginated(ui):
    ui.st.radio.side_effect = None
    ui.st.radio.return_value = "FactureFournisseur"
    ui.db.fetch_data_paginated.side_effect = lambda name, **kw: (
        _supplier_invoices().to_dict(orient="records") if name == "factures_fournisseurs" else []
    )
    ui.mod._allocation_tab("USR-1", True, _payments())
    names = [c.args[0] for c in ui.db.fetch_data_paginated.call_args_list]
    assert names == ["factures_fournisseurs", "lettrage"]


def test_database_errors_block_financial_action(ui):
    ui.db.fetch_data_paginated.side_effect = RuntimeError("database offline")
    ui.mod._allocation_tab("USR-1", True, _payments())
    ui.finance.enregistrer_lettrage.assert_not_called()


def test_payments_unknown_reference_read_error_blocked(ui):
    ui.db.fetch_data_paginated.side_effect = RuntimeError("database offline")
    ui.mod._payment_tab("USR-1", True, _accounts())
    ui.finance.enregistrer_reglement.assert_not_called()


def test_scf_balance_vue_refusee_sans_droit_specifique(ui):
    ui.roles.has_permission.side_effect = lambda role, module, permission: module != "SCF"
    ui.mod._scf_balance_tab("USR-1")
    ui.st.button.assert_not_called()
    ui.st.info.assert_called()


def test_scf_balance_aucune_lecture_avant_action(ui):
    ui.mod._scf_balance_tab("USR-1")
    ui.st.button.assert_called_once_with("Charger la balance SCF", key="finance_scf_load")
    ui.st.metric.assert_not_called()


def test_scf_balance_lecture_a_la_demande_sans_ecriture(ui, monkeypatch):
    scf = types.ModuleType("core.scf_service")
    scf.LectureSCFIndisponible = type("LectureSCFIndisponible", (ValueError,), {})
    scf.lire_balance_scf = MagicMock(return_value={
        "pieces": 1, "lignes": 2,
        "balance": {
            "411001": {"debit": "100", "credit": "0", "solde": "100"},
            "701001": {"debit": "0", "credit": "100", "solde": "-100"},
        },
    })
    monkeypatch.setitem(sys.modules, "core.scf_service", scf)
    ui.st.button.return_value = True
    ui.mod._scf_balance_tab("USR-1")
    scf.lire_balance_scf.assert_called_once_with()
    assert ui.st.metric.call_count == 2
    ui.st.dataframe.assert_called_once()
    assert ui.st.session_state["_erp_finance_interacted"] is True


def test_scf_balance_erreur_ne_diffuse_pas_de_total(ui, monkeypatch):
    scf = types.ModuleType("core.scf_service")
    scf.LectureSCFIndisponible = type("LectureSCFIndisponible", (ValueError,), {})
    scf.lire_balance_scf = MagicMock(side_effect=scf.LectureSCFIndisponible("invalid rows"))
    monkeypatch.setitem(sys.modules, "core.scf_service", scf)
    ui.st.button.return_value = True
    ui.mod._scf_balance_tab("USR-1")
    ui.st.metric.assert_not_called()
    ui.st.dataframe.assert_not_called()
    ui.st.error.assert_called()


def test_quittances_ne_lit_rien_avant_clic(ui):
    ui.mod._quittances_rapprochement_tab("USR-1")
    ui.db.get_supabase_client.assert_not_called()
    ui.st.metric.assert_not_called()
    ui.st.dataframe.assert_not_called()


def test_quittances_refuse_autorisation_revoquee(ui):
    ui.st.button.return_value = True
    ui.roles.has_permission.return_value = False
    ui.mod._quittances_rapprochement_tab("USR-1")
    ui.db.get_supabase_client.assert_called()
    ui.db.fetch_data_paginated.assert_not_called()
    ui.st.metric.assert_not_called()


def test_quittances_lecture_seule_sur_clic(ui, monkeypatch):
    stub = types.ModuleType("core.quittances_rapprochement")
    stub.RapprochementIndisponible = type("RapprochementIndisponible", (ValueError,), {})
    stub.rapprocher_reglements_clients = MagicMock(return_value={
        "nombre_reglements": 1, "montant_encaisse_total": "100.00",
        "reglements": [{
            "reglement_id": "REG-1", "client_id": "CLIENT-1",
            "date_reglement": "2026-10-28", "mode_paiement": "ESPECES",
            "montant_encaisse": "100.00", "montant_alloue": "50.00",
            "reste_a_affecter": "50.00", "statut": "ETAT_INTERNE_NON_QUITTANCE",
            "factures": [{"facture_id": "FAC-1", "montant_applique": "50.00"}],
        }],
    })
    monkeypatch.setitem(sys.modules, "core.quittances_rapprochement", stub)
    ui.mod._lecture_complete_quittances = MagicMock(side_effect=[[{"reglement_id": "REG-1"}], [], []])
    ui.st.button.return_value = True
    ui.mod._quittances_rapprochement_tab("USR-1")
    assert ui.st.metric.call_count == 2
    ui.st.dataframe.assert_called_once()
    assert ui.mod._lecture_complete_quittances.call_count == 3
    assert ui.st.session_state["_erp_finance_interacted"] is True
    assert "factures_lettrées" in ui.st.dataframe.call_args.args[0].columns
    ui.finance.enregistrer_reglement.assert_not_called()
    ui.finance.enregistrer_lettrage.assert_not_called()


def test_quittances_aucun_total_partiel_si_erreur(ui, monkeypatch):
    stub = types.ModuleType("core.quittances_rapprochement")
    stub.RapprochementIndisponible = type("RapprochementIndisponible", (ValueError,), {})
    stub.rapprocher_reglements_clients = MagicMock()
    monkeypatch.setitem(sys.modules, "core.quittances_rapprochement", stub)
    ui.mod._lecture_complete_quittances = MagicMock(side_effect=ValueError("Incomplet"))
    ui.st.button.return_value = True
    ui.mod._quittances_rapprochement_tab("USR-1")
    ui.st.metric.assert_not_called()
    ui.st.dataframe.assert_not_called()
    ui.st.error.assert_called_once()


@pytest.mark.parametrize("count,rows", [
    (2, [{"reglement_id": "REG-1"}]),
    (None, []),
    (1, [{"reglement_id": "REG-1"}, {"reglement_id": "REG-2"}]),
])
def test_quittances_refuse_pagination_incomplete(ui, count, rows):
    client = ui.db.get_supabase_client.return_value
    q = client.table.return_value.select.return_value.range.return_value
    q.execute.return_value = types.SimpleNamespace(data=rows, count=count)
    with pytest.raises(ValueError):
        ui.mod._lecture_complete_quittances("reglements", "reglement_id")


def test_quittances_refuse_table_hors_liste(ui):
    with pytest.raises(ValueError):
        ui.mod._lecture_complete_quittances("users", "user_id")
    ui.db.get_supabase_client.assert_not_called()


def test_accuse_interne_reprise_sans_doublon(ui):
    ui.mod._start_operation("receipt", "USR-1", {"reglement_id":"REG-1"})
    key=ui.mod._op_key("receipt","USR-1")
    record=ui.st.session_state[key]
    assert record["status"]=="confirmed"
    assert record["document_id"]=="RINT-1"
    assert record["operation_id"].startswith("RECUI-")
    call=ui.finance.creer_accuse_encaissement.call_args
    assert call.kwargs["operation_id"]==record["operation_id"]


def test_accuse_interne_timeout_garde_operation(ui):
    fn=ui.finance.creer_accuse_encaissement
    fn.side_effect=RuntimeError("Timeout ambigu")
    ui.mod._start_operation("receipt","USR-1", {"reglement_id":"REG-1"})
    record=ui.st.session_state[ui.mod._op_key("receipt","USR-1")]
    assert record["status"]=="uncertain"
    ident=record["operation_id"]
    fn.side_effect=None
    fn.return_value="RINT-1"
    ui.mod._execute_operation("receipt","USR-1")
    assert record["status"]=="confirmed"
    assert all(c.kwargs["operation_id"]==ident for c in fn.call_args_list)


def test_accuses_refuse_ecriture_en_lecture_seule(ui):
    ui.mod._accuses_internes_tab("USR-1", False, _payments())
    ui.finance.creer_accuse_encaissement.assert_not_called()


def test_accuses_nouveau_reglement_emet_une_seule_fois(ui):
    ui.db.fetch_data_paginated.return_value=[]
    ui.st.button.return_value=True
    ui.mod._accuses_internes_tab("USR-1", True, _payments())
    ui.finance.creer_accuse_encaissement.assert_called_once()
    assert ui.finance.creer_accuse_encaissement.call_args.kwargs["reglement_id"] == "REG-1"


def test_audit_finance_scf_charge_uniquement_sur_clic(ui):
    ui.mod._audit_finance_vers_scf_tab("USR-1", _accounts(), _payments())
    ui.db.fetch_data_paginated.assert_not_called()
    ui.st.metric.assert_not_called()


def test_audit_finance_scf_refuse_permission_revoquee(ui):
    ui.st.button.return_value = True
    ui.roles.has_permission.return_value = False
    ui.mod._audit_finance_vers_scf_tab("USR-1", _accounts(), _payments())
    ui.db.fetch_data_paginated.assert_not_called()
    ui.st.metric.assert_not_called()


def test_audit_finance_scf_ne_poste_aucune_ecriture(ui, monkeypatch):
    stub = types.ModuleType("core.rapprochement_finance_scf")
    stub.AuditTresorerieIndisponible = type(
        "AuditTresorerieIndisponible", (ValueError,), {}
    )
    stub.auditer_reglements_vers_scf = MagicMock(return_value={
        "reglements_rpc_valides": 1,
        "reglements_historiques_hors_controle": 0,
        "montant_encaisse": "150.00",
        "montant_decaisse": "0.00",
        "ecritures": [{
            "reglement_id": "REGF-1", "date_ecriture": "2026-10-29",
            "sens": "ENCAISSEMENT", "montant": "150.00",
            "total_debit": "150.00", "total_credit": "150.00",
            "statut": "VERIFIE_FINANCE_NON_COMPTABILISE_SCF",
            "lignes": [
                {"compte_finance": "CPT-1", "numero_compte_saisi": "512"},
                {"compte_finance": "CPT-2", "numero_compte_saisi": "411"},
            ],
        }],
    })
    monkeypatch.setitem(sys.modules, "core.rapprochement_finance_scf", stub)
    ui.st.button.return_value = True
    ui.mod._load_table = MagicMock(return_value=pd.DataFrame([
        {"ecriture_id": "E1", "document_source_id": "REGF-1"}
    ]))
    ui.mod._audit_finance_vers_scf_tab("USR-1", _accounts(), _payments())
    stub.auditer_reglements_vers_scf.assert_called_once()
    assert ui.st.metric.call_count == 3
    ui.st.dataframe.assert_called_once()
    ui.finance.enregistrer_reglement.assert_not_called()
    ui.finance.enregistrer_lettrage.assert_not_called()
    ui.finance.creer_accuse_encaissement.assert_not_called()


def test_audit_finance_scf_refuse_donnees_incompletes(ui, monkeypatch):
    stub = types.ModuleType("core.rapprochement_finance_scf")
    stub.AuditTresorerieIndisponible = type(
        "AuditTresorerieIndisponible", (ValueError,), {}
    )
    stub.auditer_reglements_vers_scf = MagicMock(
        side_effect=stub.AuditTresorerieIndisponible("Incomplet")
    )
    monkeypatch.setitem(sys.modules, "core.rapprochement_finance_scf", stub)
    ui.st.button.return_value = True
    ui.mod._load_table = MagicMock(return_value=pd.DataFrame())
    ui.mod._audit_finance_vers_scf_tab("USR-1", _accounts(), _payments())
    ui.st.metric.assert_not_called()
    ui.st.dataframe.assert_not_called()
    ui.st.error.assert_called_once()
