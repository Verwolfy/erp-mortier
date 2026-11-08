"""LOT-07 Achats : les panneaux inactifs ne lisent ni ne créent d'opération."""
from __future__ import annotations

from unittest.mock import MagicMock
import pandas as pd

from tests.test_achats_views_security import ui


def _choose(ui, panel):
    ui.st.selectbox.side_effect = (
        lambda label, options, **_kw:
        panel if label == "Vue Achats" else "CMA-1"
    )


def test_history_without_explicit_load_does_not_fetch_business_data(ui):
    _choose(ui, "📋 Historique & Suivi")
    ui.mod.get_fournisseurs_actifs = MagicMock(return_value=pd.DataFrame())
    ui.mod.get_mp_actives = MagicMock(return_value=pd.DataFrame())
    ui.mod.show_achats_page()
    ui.achats.get_commandes.assert_not_called()
    ui.achats.get_bons_reception.assert_not_called()
    ui.mod.get_fournisseurs_actifs.assert_not_called()
    ui.mod.get_mp_actives.assert_not_called()
    ui.db.fetch_data.assert_not_called()
    ui.st.form.assert_not_called()
    ui.st.tabs.assert_not_called()
    assert ui.st.button.call_args.args == ("Afficher l'historique Achats",)


def test_receipt_panel_does_not_execute_order_creation_or_history(ui):
    _choose(ui, "📦 Réception & Entrée Stock")
    ui.mod.get_fournisseurs_actifs = MagicMock(return_value=pd.DataFrame())
    ui.mod.get_mp_actives = MagicMock(return_value=pd.DataFrame())
    ui.mod.show_achats_page()
    ui.achats.get_commandes.assert_called_once()
    ui.mod.get_fournisseurs_actifs.assert_not_called()
    ui.mod.get_mp_actives.assert_not_called()
    ui.st.form.assert_not_called()
    ui.st.tabs.assert_not_called()


def test_order_panel_does_not_fetch_receivable_orders(ui):
    _choose(ui, "➕ Nouvelle Commande")
    ui.mod.get_fournisseurs_actifs = MagicMock(return_value=pd.DataFrame())
    ui.mod.get_mp_actives = MagicMock(return_value=pd.DataFrame())
    ui.mod.show_achats_page()
    ui.mod.get_fournisseurs_actifs.assert_called_once()
    ui.mod.get_mp_actives.assert_called_once()
    ui.achats.get_commandes.assert_not_called()
    ui.achats.get_bons_reception.assert_not_called()
    ui.st.tabs.assert_not_called()


def test_readonly_history_available_without_mutation_or_reception(ui):
    _choose(ui, "📋 Historique & Suivi")
    ui.roles.has_permission.side_effect = lambda _role, _module, kind: kind == "lecture"
    ui.mod.show_achats_page()
    ui.achats.get_commandes.assert_not_called()
    ui.achats.creer_bon_reception.assert_not_called()
    ui.achats.create_commande_achat.assert_not_called()
    ui.st.form.assert_not_called()


def test_denied_user_does_not_reach_selector_or_business_reads(ui):
    ui.roles.has_permission.return_value = False
    ui.mod.show_achats_page()
    ui.st.selectbox.assert_not_called()
    ui.achats.get_commandes.assert_not_called()
    ui.db.fetch_data.assert_not_called()


def test_navigation_callback_marks_activity_without_session_extension(ui):
    _choose(ui, "📋 Historique & Suivi")
    ui.mod.show_achats_page()
    view_call = ui.st.selectbox.call_args
    assert view_call.args[0] == "Vue Achats"
    assert len(view_call.args[1]) == 3
    assert view_call.kwargs["on_change"] is ui.mod._mark_achats_activity
    ui.mod._mark_achats_activity()
    assert ui.st.session_state["_erp_achats_interacted"] is True
    assert "last_activity" not in ui.st.session_state
