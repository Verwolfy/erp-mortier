"""Actions en ligne du BC fournisseur : tests sans lecture DB ni mutations."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def actions(monkeypatch):
    st = MagicMock()
    st.session_state = {}
    monkeypatch.setitem(sys.modules, "streamlit", st)
    source = Path(__file__).resolve().parents[1] / "modules/achats/po_row_actions.py"
    spec = importlib.util.spec_from_file_location("achats_po_row_actions_test", source)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, st


def test_clicked_row_targets_exact_order(actions):
    mod, st = actions
    key = "clicked"
    st.session_state[key] = {"row": 1, "label": "PDF"}
    mod._on_click("USR-1", "pdf", ("CMA-0003", "CMA-0002"), key)
    assert st.session_state[mod._selection_key("USR-1")] == ("pdf", "CMA-0002")


@pytest.mark.parametrize("bad", [{"row": -1}, {"row": 9}, {"row": True},
                                 {"label": "PDF"}, None, {"row": "0"}])
def test_invalid_click_never_selects_other_order(actions, bad):
    mod, st = actions
    st.session_state["clicked"] = bad
    mod._on_click("USR-1", "imprimer", ("CMA-0003", "CMA-0002"), "clicked")
    assert mod._selection_key("USR-1") not in st.session_state


def test_three_button_columns_next_to_identifier(actions):
    mod, st = actions
    rows = [{"commande_achat_id": "CMA-0003", "montant_total_local": 160000},
            {"commande_achat_id": "CMA-0002", "montant_total_local": 200}]
    mod.show_purchase_orders_with_actions(rows, "USR-1")
    args = st.dataframe.call_args
    assert args.kwargs["column_order"][:4] == [
        "commande_achat_id", "Consulter", "Imprimer", "PDF"]
    assert set(args.kwargs["column_config"]) == {"Consulter", "Imprimer", "PDF"}
    assert st.column_config.ButtonColumn.call_count == 3
    assert "achats_po_selected_USR-1" not in st.session_state


def test_reject_duplicate_order_ids(actions):
    mod, st = actions
    rows = [{"commande_achat_id": "CMA-1"}, {"commande_achat_id": "CMA-1"}]
    mod.show_purchase_orders_with_actions(rows, "USR-1")
    st.error.assert_called_once()
    st.column_config.ButtonColumn.assert_not_called()


def test_stale_selection_cleared_when_order_not_on_page(actions):
    mod, st = actions
    st.session_state[mod._selection_key("USR-1")] = ("pdf", "OTHER")
    mod.show_purchase_orders_with_actions([{"commande_achat_id": "CMA-1"}], "USR-1")
    assert mod._selection_key("USR-1") not in st.session_state
