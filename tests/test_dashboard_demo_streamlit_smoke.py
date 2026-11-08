"""Smoke AppTest des 9 vues KPI en DEMO, rendues une seule à la fois.

Aucune connexion Supabase. Les tests de service vérifient les formules ;
AppTest vérifie la navigation et le rendu réel des widgets.
"""
from __future__ import annotations

import ast
import inspect
from datetime import datetime

from streamlit.testing.v1 import AppTest

from modules.dashboards import service, views


def _forbid_supabase(*_args, **_kwargs):
    raise AssertionError("Une lecture Supabase est interdite en démo")


def test_all_nine_panels_render_demo_without_db_or_exceptions(monkeypatch):
    monkeypatch.setattr(views, "has_permission", lambda *_args, **_kw: True)
    monkeypatch.setattr(service, "fetch_data", _forbid_supabase)
    monkeypatch.setattr(service, "fetch_data_by_date_range", _forbid_supabase)

    script = """
import streamlit as st
from modules.dashboards.views import show_dashboards_page

st.session_state["user"] = {"role": "ADMIN"}
st.session_state["_erp_dashboard_demo_mode"] = True
show_dashboards_page()
"""
    at = AppTest.from_string(script, default_timeout=45).run()
    labels = list(views._DASHBOARD_PANELS)
    assert len(labels) == 9

    # Contrairement aux st.tabs, une sélection calcule uniquement la vue active.
    # Chaque passage oblige à réexécuter la véritable interface Streamlit.
    total_metrics = 0
    for label in labels:
        if at.selectbox[0].value != label:
            at = at.selectbox[0].set_value(label).run()
        assert len(at.exception) == 0, [e.message for e in at.exception]
        assert at.selectbox[0].value == label
        assert list(at.selectbox[0].options) == labels
        assert len(at.tabs) == 0, "Les anciens onglets exécutent tout en parallèle"
        assert 1 <= len(at.metric) <= 4, (
            label, "la vue active ne doit pas afficher les KPI des autres vues"
        )
        total_metrics += len(at.metric)
        assert any("MODE DÉMONSTRATION" in str(item.value)
                   for item in at.warning), "Bannière démo absente"
        assert not any("Erreur" in str(item.value) for item in at.error)

    assert total_metrics >= 20


def test_demo_selector_precedes_panel_navigation_in_streamlit_layout():
    source = inspect.getsource(views._show_dashboards_page_impl)
    tree = ast.parse(source)
    toggles, selectors = [], []
    for node in ast.walk(tree):
        if (not isinstance(node, ast.Call)
                or not isinstance(node.func, ast.Attribute)
                or not isinstance(node.func.value, ast.Name)
                or node.func.value.id != "st"):
            continue
        if node.func.attr == "toggle":
            toggles.append(node)
        if (node.func.attr == "selectbox" and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == "Vue du tableau de bord"):
            selectors.append(node)
    assert len(toggles) == 1 and len(selectors) == 1
    assert toggles[0].lineno < selectors[0].lineno


def test_default_calendar_uses_erp_clock(monkeypatch):
    monkeypatch.setattr(views, "get_local_now",
                        lambda: datetime(2026, 12, 1, 0, 5))
    assert str(views._dashboard_today()) == "2026-12-01"
    assert str(views._current_month_end(views._dashboard_today())) == "2026-12-31"
