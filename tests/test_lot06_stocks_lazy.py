"""Lot 06 Stocks : navigation paresseuse, droits et chargement à la demande.

Reprend la fixture d'écran sécurisée : aucun Supabase réel, aucune écriture.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
from tests.test_stocks_views_security import ui


def _choose(ui, label):
    ui.st.selectbox.side_effect = (
        lambda name, options, **_kw:
        label if name == "Vue Stocks" else list(options)[0]
    )


def test_only_history_panel_renders_without_referential_or_stock_reads(ui):
    _choose(ui, "📋 Historique des Mouvements")
    ui.mod.get_mp_actives = MagicMock(return_value=pd.DataFrame())
    ui.mod.get_skus_actifs = MagicMock(return_value=pd.DataFrame())
    ui.mod.get_produits = MagicMock(return_value=pd.DataFrame())
    ui.mod.show_stocks_page()
    ui.mod.get_mp_actives.assert_not_called()
    ui.mod.get_skus_actifs.assert_not_called()
    ui.mod.get_produits.assert_not_called()
    ui.stocks.get_stock_actuel_mp.assert_not_called()
    ui.stocks.get_stock_actuel_pf.assert_not_called()
    ui.st.form.assert_not_called()
    ui.st.tabs.assert_not_called()
    assert ui.st.button.call_args.args[0] == "Afficher les mouvements de stock"


def test_entry_panel_does_not_compute_stock_kpis_or_histories(ui):
    _choose(ui, "🔄 Entrée Manuelle (hors BR)")
    ui.mod.get_mp_actives = MagicMock(return_value=pd.DataFrame())
    ui.mod.get_skus_actifs = MagicMock(return_value=pd.DataFrame())
    ui.mod.get_produits = MagicMock(return_value=pd.DataFrame())
    ui.mod.show_stocks_page()
    ui.mod.get_mp_actives.assert_called_once()
    ui.stocks.get_stock_actuel_mp.assert_not_called()
    ui.stocks.get_stock_actuel_pf.assert_not_called()
    ui.mod.get_skus_actifs.assert_not_called()
    ui.mod.get_produits.assert_not_called()
    ui.st.tabs.assert_not_called()
    ui.st.button.assert_not_called()


def test_stock_state_renders_only_stock_panel_without_entry_form(ui):
    _choose(ui, "📊 État des Stocks")
    ui.mod.get_mp_actives = MagicMock(return_value=pd.DataFrame())
    ui.mod.show_stocks_page()
    ui.mod.get_mp_actives.assert_called_once()
    ui.stocks.get_stock_actuel_mp.assert_called_once()
    ui.stocks.get_stock_actuel_pf.assert_not_called()
    ui.st.form.assert_not_called()
    ui.st.button.assert_not_called()


def test_readonly_entry_never_fetches_catalogue_or_renders_form(ui):
    _choose(ui, "🔄 Entrée Manuelle (hors BR)")
    ui.roles.has_permission.side_effect = lambda _role, _module, mode: mode == "lecture"
    ui.mod.get_mp_actives = MagicMock(return_value=pd.DataFrame())
    ui.mod.show_stocks_page()
    ui.mod.get_mp_actives.assert_not_called()
    ui.st.form.assert_not_called()
    ui.st.warning.assert_called()


def test_navigation_denied_before_selector_or_read(ui):
    _choose(ui, "📊 État des Stocks")
    ui.roles.has_permission.side_effect = lambda *_args: False
    ui.mod.get_mp_actives = MagicMock(return_value=pd.DataFrame())
    ui.mod.show_stocks_page()
    ui.st.selectbox.assert_not_called()
    ui.mod.get_mp_actives.assert_not_called()
    ui.stocks.get_stock_actuel_mp.assert_not_called()
    ui.stocks.get_stock_actuel_pf.assert_not_called()


def test_navigation_tracks_activity_without_renewing_session(ui):
    _choose(ui, "📊 État des Stocks")
    ui.mod.get_mp_actives = MagicMock(return_value=pd.DataFrame())
    ui.mod.show_stocks_page()
    calls = [call for call in ui.st.selectbox.call_args_list
             if call.args and call.args[0] in {"Vue Stocks", "Catégorie de stock"}]
    assert [call.args[0] for call in calls] == ["Vue Stocks", "Catégorie de stock"]
    assert all(len(call.args[1]) == 3 for call in calls)
    assert all(call.kwargs["on_change"] is ui.mod._mark_stocks_activity
               for call in calls)
    ui.mod._mark_stocks_activity()
    assert ui.st.session_state["_erp_stocks_interacted"] is True
    assert "last_activity" not in ui.st.session_state
