"""Lot 11 Finance : seuls les appels nécessaires au panneau sélectionné sont lancés.

Aucune base réelle ni mutation, mêmes contrôles de permission que le module.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from tests.test_finance_views_security import ui


PANELS = (
    "📊 Tableau de bord", "🏦 Comptes", "💸 Règlements",
    "🔗 Lettrage", "📖 Journal des écritures",
    "📚 Balance SCF (lecture seule)", "🧾 Rapprochement quittances",
    "🧾 Accusés internes", "📒 Pré-audit Finance → SCF",
    "🔎 Préparation TVA / SCF", "🔗 Correspondances Finance / SCF",
)
VIEWS = (
    "_dashboard", "_accounts_tab", "_payment_tab",
    "_allocation_tab", "_journal",
    "_scf_balance_tab", "_quittances_rapprochement_tab",
    "_accuses_internes_tab", "_audit_finance_vers_scf_tab",
    "_preflight_reglementaire_tab", "_correspondances_finance_scf_tab",
)
ACCOUNT_VIEWS = {1, 2, 8, 10}
PAYMENT_VIEWS = {0, 3, 7, 8}


def select(ui, idx):
    ui.st.selectbox.side_effect = (
        lambda label, options, **_kw:
        PANELS[idx] if label == "Vue Finance" else list(options)[0]
    )


@pytest.mark.parametrize("index", range(11))
def test_eleven_views_only_load_required_tables_and_one_panel(ui, index):
    select(ui, index)
    for name in VIEWS:
        setattr(ui.mod, name, MagicMock())
    ui.mod.show_finance_page()

    expected = []
    if index in ACCOUNT_VIEWS:
        expected.append("comptes")
    if index in PAYMENT_VIEWS:
        expected.append("reglements")
    if index == 4:
        expected.append("ecritures_comptables")
    assert [c.args[0] for c in ui.db.fetch_data_paginated.call_args_list] == expected
    for k, name in enumerate(VIEWS):
        assert getattr(ui.mod, name).call_count == (1 if k == index else 0)
    ui.st.tabs.assert_not_called()


@pytest.mark.parametrize("index", [5, 6, 9])
def test_readonly_diagnostics_do_not_download_account_or_payment_lists(ui, index):
    select(ui, index)
    ui.db.fetch_data_paginated.side_effect = AssertionError(
        "Le diagnostic consultatif ne nécessite pas de lecture initiale")
    for name in VIEWS:
        setattr(ui.mod, name, MagicMock())
    ui.mod.show_finance_page()
    ui.db.fetch_data_paginated.assert_not_called()
    getattr(ui.mod, VIEWS[index]).assert_called_once()
    ui.st.error.assert_not_called()


def test_readonly_account_view_has_no_write_right(ui):
    select(ui, 1)
    ui.roles.has_permission.side_effect = lambda _r, _m, kind: kind == "lecture"
    ui.mod._accounts_tab = MagicMock()
    ui.mod.show_finance_page()
    args = ui.mod._accounts_tab.call_args.args
    assert args[0] == "USR-1"
    assert args[1] is False
    assert isinstance(args[2], pd.DataFrame)
    ui.finance.creer_compte.assert_not_called()


def test_denied_session_blocks_all_navigation_and_reads(ui):
    select(ui, 0)
    ui.st.session_state["authenticated"] = False
    ui.mod.show_finance_page()
    ui.st.selectbox.assert_not_called()
    ui.db.fetch_data_paginated.assert_not_called()
    ui.finance.enregistrer_reglement.assert_not_called()


def test_failed_selected_source_does_not_render_any_finance_view(ui):
    select(ui, 3)
    ui.db.fetch_data_paginated.side_effect = RuntimeError(
        "Message de source sensible, à ne pas afficher")
    for name in VIEWS:
        setattr(ui.mod, name, MagicMock())
    ui.mod.show_finance_page()
    for name in VIEWS:
        getattr(ui.mod, name).assert_not_called()
    ui.st.error.assert_called_once_with(
        "Données Finance indisponibles ; aucune modification possible.")
    assert "sensible" not in str(ui.st.error.call_args)


def test_navigation_is_activity_only_and_exposes_eleven_views(ui):
    select(ui, 9)
    ui.mod._preflight_reglementaire_tab = MagicMock()
    ui.mod.show_finance_page()
    navigation = next(c for c in ui.st.selectbox.call_args_list
                      if c.args and c.args[0] == "Vue Finance")
    assert tuple(navigation.args[1]) == PANELS
    assert navigation.kwargs["on_change"] is ui.mod._mark_finance_activity
    ui.mod._mark_finance_activity()
    assert ui.st.session_state["_erp_finance_interacted"] is True
    assert "last_activity" not in ui.st.session_state
