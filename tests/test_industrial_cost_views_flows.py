"""Tests du parcours Streamlit des couts industriels, sans donnees ni identifiants reels.

L'interface est importee avec st et le service remplaces par des doublures.
"""
from __future__ import annotations

import importlib.util
import sys
import types
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

PATH = Path(__file__).resolve().parents[1] / "modules" / "production" / "cost_views.py"


@pytest.fixture
def ui(monkeypatch):
    st = MagicMock()
    st.form_submit_button.return_value = False
    st.button.return_value = False
    st.checkbox.return_value = False
    st.date_input.return_value = date(2026, 11, 6)
    st.selectbox.side_effect = lambda _label, values, **_kw: list(values)[0]
    st.number_input.return_value = 5
    st.text_input.return_value = "TEST"
    st.text_area.return_value = "Motif de test suffisamment detaille"

    service = types.ModuleType("modules.production.cost_service")
    for name in ("list_periods", "list_natures", "get_period_report", "can_manage_costs",
                 "create_period", "create_nature", "add_pool", "document_pool",
                 "set_driver", "validate_period"):
        setattr(service, name, MagicMock())
    service.BASES = ("UNITS", "KG", "HOURS_LABOR", "HOURS_MACHINE", "KWH", "DIRECT_COST")
    service.list_periods.return_value = [{
        "period_id": "P-TEST", "libelle": "Novembre", "statut": "BROUILLON",
        "date_debut": "2026-11-01", "date_fin": "2026-11-30",
    }]
    service.list_natures.return_value = [{"nature_code": "ENERGIE", "libelle": "Energie"}]
    service.get_period_report.return_value = {
        "pools": [], "drivers": [], "allocations": [], "summaries": [],
        "scf_reconciliation": [], "audit": {"audit_ok": False},
    }
    service.can_manage_costs.return_value = True

    monkeypatch.setitem(sys.modules, "streamlit", st)
    monkeypatch.setitem(sys.modules, "modules.production.cost_service", service)
    spec = importlib.util.spec_from_file_location("_cost_views_under_test", PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return types.SimpleNamespace(view=mod, st=st, svc=service)


def _assert_no_writes(svc):
    for name in ("create_period", "create_nature", "add_pool", "document_pool",
                 "set_driver", "validate_period"):
        getattr(svc, name).assert_not_called()


def test_read_only_profile_never_exposes_forms(ui):
    ui.view.show_cost_reference(False)
    ui.st.form.assert_not_called()
    ui.st.button.assert_not_called()
    _assert_no_writes(ui.svc)
    ui.svc.can_manage_costs.assert_not_called()


def test_finance_write_denied_hides_forms_even_if_production_can_write(ui):
    ui.svc.can_manage_costs.return_value = False
    ui.view.show_cost_reference(True)
    ui.svc.can_manage_costs.assert_called_once_with()
    ui.st.form.assert_not_called()
    _assert_no_writes(ui.svc)


def test_read_failure_fails_closed(ui):
    ui.svc.list_periods.side_effect = PermissionError("Finance denied")
    ui.view.show_cost_reference(True)
    ui.st.error.assert_called()
    ui.st.form.assert_not_called()
    _assert_no_writes(ui.svc)


def test_report_error_does_not_write(ui):
    ui.svc.get_period_report.side_effect = RuntimeError("unavailable")
    ui.view.show_cost_reference(False)
    ui.st.error.assert_called_once()
    _assert_no_writes(ui.svc)


def test_incomplete_report_blocks_all_write_forms(ui):
    ui.svc.get_period_report.side_effect = ConnectionError("last page unavailable")
    ui.view.show_cost_reference(True)
    ui.st.error.assert_called()
    ui.st.form.assert_not_called()
    _assert_no_writes(ui.svc)


def test_locked_period_has_no_edit_form(ui):
    ui.svc.list_periods.return_value[0]["statut"] = "VALIDE"
    ui.view.show_cost_reference(True)
    ui.st.form.assert_called_once_with("cost_create_period")
    ui.svc.validate_period.assert_not_called()


def test_no_period_still_offers_creation_to_writer(ui):
    ui.svc.list_periods.return_value = []
    ui.view.show_cost_reference(True)
    ui.st.form.assert_called_once_with("cost_create_period")


def test_no_active_natures_is_handled(ui):
    ui.svc.list_natures.return_value = []
    ui.view.show_cost_reference(True)
    # This must never raise IndexError from empty selectbox.
    _assert_no_writes(ui.svc)


def test_validate_requires_explicit_ack(ui):
    ui.st.checkbox.return_value = False
    ui.st.button.return_value = False
    ui.view.show_cost_reference(True)
    ui.svc.validate_period.assert_not_called()
    assert any(k.get("disabled") is True for c,k in
               ((a.args,a.kwargs) for a in ui.st.button.call_args_list))


def test_approved_validation_calls_rpc(ui):
    ui.st.checkbox.return_value = True
    ui.st.button.side_effect = lambda label, **_kw: label == "Valider la période"
    ui.svc.validate_period.return_value = {"audit_ok": True}
    ui.view.show_cost_reference(True)
    ui.svc.validate_period.assert_called_once_with("P-TEST")
    ui.st.success.assert_called()


def test_validation_error_never_claims_success(ui):
    ui.st.checkbox.return_value = True
    ui.st.button.side_effect = lambda label, **_kw: label == "Valider la période"
    ui.svc.validate_period.side_effect = ValueError("audit refused")
    ui.view.show_cost_reference(True)
    ui.st.error.assert_called()
    ui.st.success.assert_not_called()


def test_documenting_pool_sends_scf_piece_line_and_reason(ui):
    ui.st.form_submit_button.side_effect = lambda label: label == "Documenter la charge"
    ui.st.text_input.side_effect = lambda label, **kw: {
        "Identifiant du pool analytique": "POOL-TEST",
        "UUID de la pièce SCF validée": "11111111-1111-4111-8111-111111111111",
    }.get(label, "TEST")
    ui.st.number_input.side_effect = lambda label, **_kw: 42
    ui.view.show_cost_reference(True)
    ui.svc.document_pool.assert_called_once_with(
        "P-TEST", "POOL-TEST", "11111111-1111-4111-8111-111111111111",
        42, "Motif de test suffisamment detaille")


def test_documenting_error_does_not_claim_success(ui):
    ui.st.form_submit_button.side_effect = lambda label: label == "Documenter la charge"
    ui.svc.document_pool.side_effect = ValueError("invalid SCF")
    ui.view.show_cost_reference(True)
    ui.st.success.assert_not_called()
    ui.st.error.assert_called()


def test_creation_of_period_keeps_dates(ui):
    ui.st.form_submit_button.side_effect = lambda label: label == "Créer la période"
    ui.svc.create_period.return_value = "NEW-PERIOD"
    ui.view.show_cost_reference(True)
    ui.svc.create_period.assert_called_once_with("TEST", "2026-11-06", "2026-11-06")


def test_pool_creation_starts_in_simulation(ui):
    ui.st.form_submit_button.side_effect = lambda label: label == "Enregistrer la charge"
    ui.st.text_input.side_effect = lambda label, **kw: "5" if label == "Montant analytique (DZD)" else "TEST"
    ui.view.show_cost_reference(True)
    ui.svc.add_pool.assert_called_once_with(
        "P-TEST", "ENERGIE", "UNITS", "5", "TEST")


def test_driver_uses_selected_basis_and_of(ui):
    ui.st.form_submit_button.side_effect = lambda label: label == "Enregistrer l'assiette"
    ui.st.text_input.side_effect = lambda label, **kw: "5" if label == "Valeur de la clé" else "TEST"
    ui.view.show_cost_reference(True)
    ui.svc.set_driver.assert_called_once_with(
        "P-TEST", "TEST", "UNITS", "5", "TEST")


def test_create_nature_does_not_create_charge(ui):
    ui.st.form_submit_button.side_effect = lambda label: label == "Créer la nature"
    ui.view.show_cost_reference(True)
    ui.svc.create_nature.assert_called_once_with(
        "TEST", "TEST", "Motif de test suffisamment detaille")
    ui.svc.add_pool.assert_not_called()


def test_six_decimal_amount_kept_exact(ui):
    ui.st.form_submit_button.side_effect = lambda label: label == "Enregistrer la charge"
    ui.st.text_input.side_effect = lambda label, **kw: (
        "0.123456" if label == "Montant analytique (DZD)" else "TEST")
    ui.view.show_cost_reference(True)
    ui.svc.add_pool.assert_called_once_with(
        "P-TEST", "ENERGIE", "UNITS", "0.123456", "TEST")


def test_six_decimal_driver_kept_exact(ui):
    ui.st.form_submit_button.side_effect = lambda label: label == "Enregistrer l'assiette"
    ui.st.text_input.side_effect = lambda label, **kw: (
        "0.123456" if label == "Valeur de la clé" else "TEST")
    ui.view.show_cost_reference(True)
    ui.svc.set_driver.assert_called_once_with(
        "P-TEST", "TEST", "UNITS", "0.123456", "TEST")


def test_validated_period_displays_snapshot_drift_warning(ui):
    ui.svc.list_periods.return_value[0]["statut"] = "VALIDE"
    ui.svc.get_period_report.return_value["validation_drift"] = [{
        "of_id": "OF-TEST", "derive_detectee": True,
        "cout_direct_valide_dzd": "100", "cout_direct_actuel_dzd": "101",
    }]
    ui.st.selectbox.side_effect = lambda label, values, **kw: (
        "validation_drift" if label == "Section du rapport" else list(values)[0])
    ui.view.show_cost_reference(False)
    ui.st.error.assert_called_once()
    ui.st.form.assert_not_called()
    ui.svc.validate_period.assert_not_called()


def test_validated_period_displays_conform_snapshot(ui):
    ui.svc.list_periods.return_value[0]["statut"] = "VALIDE"
    ui.svc.get_period_report.return_value["validation_drift"] = [{
        "of_id": "OF-TEST", "derive_detectee": False,
        "cout_direct_valide_dzd": "100", "cout_direct_actuel_dzd": "100",
    }]
    ui.st.selectbox.side_effect = lambda label, values, **kw: (
        "validation_drift" if label == "Section du rapport" else list(values)[0])
    ui.view.show_cost_reference(False)
    ui.st.success.assert_called_once()
    ui.st.error.assert_not_called()


def test_ui_only_requests_selected_section(ui):
    ui.view.show_cost_reference(False)
    ui.svc.get_period_report.assert_called_once_with("P-TEST", sections=("pools",))
    ui.st.dataframe.assert_called()


def test_ui_can_open_scf_section_without_other_tables(ui):
    ui.st.selectbox.side_effect = lambda label, values, **kw: (
        "scf_reconciliation" if label == "Section du rapport" else list(values)[0])
    ui.view.show_cost_reference(False)
    ui.svc.get_period_report.assert_called_once_with(
        "P-TEST", sections=("scf_reconciliation",))


def test_section_failure_hides_write_forms(ui):
    ui.svc.get_period_report.side_effect = ConnectionError("selected section unavailable")
    ui.view.show_cost_reference(True)
    ui.st.error.assert_called()
    ui.st.form.assert_not_called()
    _assert_no_writes(ui.svc)
