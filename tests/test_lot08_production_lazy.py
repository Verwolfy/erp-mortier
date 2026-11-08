"""Lot-08 : isolation des cinq vues Production, sans mutation ni réseau."""
from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

from tests.test_production_views_security import ui


RECIPE = "📝 Recettes"
ORDERS = "⚙️ OF"
FOLLOW = "📊 Production et CQ"
HISTORY = "🔍 Consommations et contrôles"
COST = "💰 Coûts industriels"


def choose(ui, panel):
    ui.st.selectbox.side_effect = (
        lambda label, options, **_kw:
        panel if label == "Vue Production" else list(options)[0]
    )
    ui.mod.get_produits_actifs = MagicMock(return_value=pd.DataFrame())
    ui.mod.get_mp_actives = MagicMock(return_value=pd.DataFrame())
    ui.mod.get_skus_actifs = MagicMock(return_value=pd.DataFrame())


def test_costs_does_not_fetch_catalogues_or_open_manufacturing_forms(ui):
    choose(ui, COST)
    ui.mod.show_production_page()
    ui.costs.show_cost_reference.assert_called_once_with(True)
    ui.mod.get_produits_actifs.assert_not_called()
    ui.mod.get_mp_actives.assert_not_called()
    ui.mod.get_skus_actifs.assert_not_called()
    ui.prod.get_recettes.assert_not_called()
    ui.prod.get_ordres_fabrication.assert_not_called()
    ui.st.form.assert_not_called()
    ui.st.tabs.assert_not_called()


def test_history_does_not_prefetch_catalogues_or_of(ui):
    choose(ui, HISTORY)
    ui.mod.show_production_page()
    ui.costs.show_cost_reference.assert_not_called()
    ui.mod.get_produits_actifs.assert_not_called()
    ui.mod.get_mp_actives.assert_not_called()
    ui.mod.get_skus_actifs.assert_not_called()
    ui.prod.get_ordres_fabrication.assert_not_called()
    ui.st.form.assert_not_called()
    ui.st.button.assert_called_once()
    assert ui.st.button.call_args.args[0] == "Afficher l'historique Production"


def test_recipe_does_not_fetch_skus_or_cost_reference(ui):
    choose(ui, RECIPE)
    ui.mod.show_production_page()
    ui.mod.get_produits_actifs.assert_called_once()
    ui.mod.get_mp_actives.assert_called_once()
    ui.mod.get_skus_actifs.assert_not_called()
    ui.costs.show_cost_reference.assert_not_called()
    ui.prod.get_ordres_fabrication.assert_not_called()


def test_of_loads_only_required_three_catalogues(ui):
    choose(ui, ORDERS)
    ui.mod.show_production_page()
    ui.mod.get_produits_actifs.assert_called_once()
    ui.mod.get_mp_actives.assert_called_once()
    ui.mod.get_skus_actifs.assert_called_once()
    ui.costs.show_cost_reference.assert_not_called()


def test_followup_loads_three_catalogues_but_not_costs(ui):
    choose(ui, FOLLOW)
    ui.mod.show_production_page()
    ui.mod.get_produits_actifs.assert_called_once()
    ui.mod.get_mp_actives.assert_called_once()
    ui.mod.get_skus_actifs.assert_called_once()
    ui.costs.show_cost_reference.assert_not_called()


def test_readonly_history_cannot_load_creation_catalogues(ui):
    choose(ui, HISTORY)
    ui.roles.has_permission.side_effect = (
        lambda _role, _module, operation: operation == "lecture"
    )
    ui.mod.show_production_page()
    ui.mod.get_produits_actifs.assert_not_called()
    ui.mod.get_mp_actives.assert_not_called()
    ui.mod.get_skus_actifs.assert_not_called()
    ui.prod.create_recette.assert_not_called()
    ui.prod.create_ordre_fabrication.assert_not_called()
    ui.prod.enregistrer_controle_qualite.assert_not_called()


def test_access_denied_before_panel_selector(ui):
    choose(ui, COST)
    ui.roles.has_permission.return_value = False
    ui.mod.show_production_page()
    ui.st.selectbox.assert_not_called()
    ui.mod.get_mp_actives.assert_not_called()
    ui.mod.get_skus_actifs.assert_not_called()
    ui.costs.show_cost_reference.assert_not_called()


def test_panel_navigation_tracks_activity_without_extending_session(ui):
    choose(ui, HISTORY)
    ui.mod.show_production_page()
    panel = next(call for call in ui.st.selectbox.call_args_list
                 if call.args and call.args[0] == "Vue Production")
    assert len(panel.args[1]) == 5
    assert panel.kwargs["on_change"] is ui.mod._mark_production_activity
    ui.mod._mark_production_activity()
    assert ui.st.session_state["_erp_production_interacted"] is True
    assert "last_activity" not in ui.st.session_state
