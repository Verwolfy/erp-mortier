"""Lot 06B: seules les données de la catégorie de stock sélectionnée sont lues."""
from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

from tests.test_stocks_views_security import ui


STOCKS = "📊 État des Stocks"
VRAC = "🧪 Matières Premières (Vrac)"
EMB = "📦 Emballages"
PF = "🛍️ Produits Finis"


def _navigate(ui, category):
    ui.st.selectbox.side_effect = (
        lambda label, options, **_kw:
        STOCKS if label == "Vue Stocks" else
        category if label == "Catégorie de stock" else list(options)[0]
    )
    ui.mod.get_mp_actives = MagicMock(return_value=pd.DataFrame())
    ui.mod.get_skus_actifs = MagicMock(return_value=pd.DataFrame())
    ui.mod.get_produits = MagicMock(return_value=pd.DataFrame())


def test_pf_only_reads_pf_and_its_own_catalogues(ui):
    _navigate(ui, PF)
    ui.mod.show_stocks_page()
    ui.stocks.get_stock_actuel_pf.assert_called_once()
    ui.mod.get_skus_actifs.assert_called_once()
    ui.mod.get_produits.assert_called_once()
    ui.stocks.get_stock_actuel_mp.assert_not_called()
    ui.mod.get_mp_actives.assert_not_called()
    ui.st.form.assert_not_called()
    ui.st.tabs.assert_not_called()


def test_vrac_only_reads_mp(ui):
    _navigate(ui, VRAC)
    ui.mod.show_stocks_page()
    ui.stocks.get_stock_actuel_mp.assert_called_once()
    ui.mod.get_mp_actives.assert_called_once()
    ui.stocks.get_stock_actuel_pf.assert_not_called()
    ui.mod.get_skus_actifs.assert_not_called()
    ui.mod.get_produits.assert_not_called()
    ui.st.tabs.assert_not_called()


def test_emballages_only_reads_mp(ui):
    _navigate(ui, EMB)
    ui.mod.show_stocks_page()
    ui.stocks.get_stock_actuel_mp.assert_called_once()
    ui.mod.get_mp_actives.assert_called_once()
    ui.stocks.get_stock_actuel_pf.assert_not_called()
    ui.mod.get_skus_actifs.assert_not_called()
    ui.mod.get_produits.assert_not_called()


def test_pf_has_no_mp_read_even_when_mp_catalogue_would_fail(ui):
    _navigate(ui, PF)
    ui.mod.get_mp_actives.side_effect = RuntimeError("MP offline")
    ui.mod.show_stocks_page()
    ui.st.error.assert_not_called()
    ui.mod.get_mp_actives.assert_not_called()
    ui.stocks.get_stock_actuel_mp.assert_not_called()


def test_rbac_blocks_both_stock_categories_before_selection(ui):
    _navigate(ui, PF)
    ui.roles.has_permission.return_value = False
    ui.mod.show_stocks_page()
    ui.st.selectbox.assert_not_called()
    ui.mod.get_mp_actives.assert_not_called()
    ui.stocks.get_stock_actuel_mp.assert_not_called()
    ui.stocks.get_stock_actuel_pf.assert_not_called()
