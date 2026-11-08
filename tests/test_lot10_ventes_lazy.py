"""Lot 10 Ventes : calculer uniquement la vue active, droits et RPC inchangés."""
from __future__ import annotations

from unittest.mock import MagicMock
import pandas as pd

from tests.test_ventes_views_security import ui


PANELS = (
    "Facture / Avoir", "Commandes clients", "Bons de livraison",
    "Suivi factures", "TVA par SKU (contrôle)",
)
CALLS = ("_draft_tab", "_order_tab", "_ship_tab",
         "_workflow_tab", "_controle_tva_sku_tab")


def choose(ui, panel):
    ui.st.selectbox.side_effect = (
        lambda label, options, **_kw:
        panel if label == "Vue Ventes" else list(options)[0]
    )
    for name in CALLS:
        setattr(ui.mod, name, MagicMock())


def test_each_panel_calls_only_one_view_and_reads_invoices_when_needed(ui):
    for i, panel in enumerate(PANELS):
        ui.sales.get_factures.reset_mock()
        choose(ui, panel)
        ui.mod.show_ventes_page()
        for j, name in enumerate(CALLS):
            assert getattr(ui.mod, name).call_count == (1 if i == j else 0)
        assert ui.sales.get_factures.call_count == (1 if i in (0, 3) else 0)
        ui.st.tabs.assert_not_called()


def test_order_panel_never_prefetches_factures_or_draft(ui):
    choose(ui, PANELS[1])
    ui.sales.get_factures.side_effect = AssertionError("Lecture factures non requise")
    ui.mod.show_ventes_page()
    ui.mod._order_tab.assert_called_once()
    ui.mod._draft_tab.assert_not_called()
    ui.mod._workflow_tab.assert_not_called()
    ui.st.error.assert_not_called()


def test_shipping_panel_never_prefetches_factures(ui):
    choose(ui, PANELS[2])
    ui.sales.get_factures.side_effect = AssertionError("Lecture factures non requise")
    ui.mod.show_ventes_page()
    ui.mod._ship_tab.assert_called_once()
    ui.st.error.assert_not_called()


def test_tva_panel_never_prefetches_factures(ui):
    choose(ui, PANELS[4])
    ui.sales.get_factures.side_effect = AssertionError("Lecture factures non requise")
    ui.mod.show_ventes_page()
    ui.mod._controle_tva_sku_tab.assert_called_once()
    ui.st.error.assert_not_called()


def test_workflow_validation_still_receives_full_invoices(ui):
    choose(ui, PANELS[3])
    data = pd.DataFrame([{"facture_id": "FAC-TEST", "statut": "BROUILLON"}])
    ui.sales.get_factures.return_value = data
    ui.mod.show_ventes_page()
    ui.sales.get_factures.assert_called_once()
    args = ui.mod._workflow_tab.call_args.args
    assert args[0] == "USR-1" and args[1] is True
    pd.testing.assert_frame_equal(args[2], data)
    ui.mod._draft_tab.assert_not_called()


def test_readonly_does_not_fetch_full_invoices_even_on_workflow(ui):
    choose(ui, PANELS[3])
    ui.roles.has_permission.side_effect = [True, False]
    ui.mod.show_ventes_page()
    ui.sales.get_factures.assert_not_called()
    assert ui.mod._workflow_tab.call_args.args[1] is False
    assert ui.mod._workflow_tab.call_args.args[2].empty


def test_denied_account_blocks_selector_before_data_access(ui):
    choose(ui, PANELS[0])
    ui.roles.has_permission.return_value = False
    ui.mod.show_ventes_page()
    ui.st.selectbox.assert_not_called()
    ui.sales.get_factures.assert_not_called()
    for name in CALLS:
        getattr(ui.mod, name).assert_not_called()


def test_navigation_callback_keeps_activity_without_session_extension(ui):
    choose(ui, PANELS[4])
    ui.mod.show_ventes_page()
    nav = next(x for x in ui.st.selectbox.call_args_list
               if x.args and x.args[0] == "Vue Ventes")
    assert tuple(nav.args[1]) == PANELS
    assert nav.kwargs["on_change"] is ui.mod._mark_ventes_activity
    ui.mod._mark_ventes_activity()
    assert ui.st.session_state["_erp_ventes_interacted"] is True
    assert "last_activity" not in ui.st.session_state
