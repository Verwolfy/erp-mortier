"""Smoke test de rendu Streamlit réel des 9 onglets KPI en mode DEMO.

AppTest exécute le code UI Streamlit et ses widgets sans navigateur. Les
graphiques ne sont pas validés pixel par pixel (limite AppTest) ; les calculs
restent couverts par test_dashboard_demo_mode.py / test_dashboard_kpi_visuals.py.
"""
from __future__ import annotations

import ast
import inspect
from datetime import datetime

from streamlit.testing.v1 import AppTest

from modules.dashboards import service, views


def _forbid_supabase(*_args, **_kwargs):
    raise AssertionError("Une lecture Supabase est interdite en démo")


def test_all_nine_tabs_render_demo_without_db_or_exceptions(monkeypatch):
    """Toute rubrique doit afficher ses KPI sans lecture réelle ni exception."""
    monkeypatch.setattr(views, "has_permission", lambda *_args, **_kw: True)
    monkeypatch.setattr(service, "fetch_data", _forbid_supabase)
    monkeypatch.setattr(service, "fetch_data_by_date_range", _forbid_supabase)

    # Le vrai st.tabs est utilisé : contrairement aux tests de service,
    # on valide ici aussi les appels st.metric / dataframe / chart / tooltip.
    script = """
import streamlit as st
from modules.dashboards.views import show_dashboards_page

st.session_state["user"] = {"role": "ADMIN"}
st.session_state["_erp_dashboard_demo_mode"] = True
show_dashboards_page()
"""
    at = AppTest.from_string(script, default_timeout=45).run()
    assert len(at.exception) == 0, [e.message for e in at.exception]
    assert len(at.tabs) == 9, [t.label for t in at.tabs]
    assert "Direction" in at.tabs[0].label
    assert "Finance" in at.tabs[-1].label
    # Vérifier une couverture réelle de métriques, pas seulement des onglets.
    assert len(at.metric) >= 20
    assert any("MODE DÉMONSTRATION" in str(item.value)
               for item in at.warning), "Bannière démo absente"
    assert not any("Erreur" in str(item.value) for item in at.error)


def test_mode_selector_precedes_tabs_in_streamlit_layout():
    """Évite un sélecteur démo placé sous les neuf panneaux."""
    source = inspect.getsource(views._show_dashboards_page_impl)
    tree = ast.parse(source)
    position = {}
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "st"
                and node.func.attr in {"toggle", "tabs"}):
            position[node.func.attr] = node.lineno
    assert position["toggle"] < position["tabs"]


def test_default_calendar_uses_erp_clock(monkeypatch):
    monkeypatch.setattr(views, "get_local_now",
                        lambda: datetime(2026, 12, 1, 0, 5))
    assert str(views._dashboard_today()) == "2026-12-01"
    assert str(views._current_month_end(views._dashboard_today())) == "2026-12-31"
