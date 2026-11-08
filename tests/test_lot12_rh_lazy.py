"""Lot 12 RH : navigation exclusive et collecte minimale (sans Supabase)."""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "modules" / "rh" / "views.py").read_text(encoding="utf-8")


def run_isolated(source: str):
    proc = subprocess.run(
        [sys.executable, "-c", source], cwd=ROOT,
        capture_output=True, text=True, timeout=45,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_rh_no_eager_tabs_and_readers_conditioned_by_active_panel():
    tree = ast.parse(SOURCE)
    page = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                and n.name == "show_rh_page")
    assert "st.tabs(" not in SOURCE
    assert 'active_panel = st.selectbox(' in SOURCE
    assert '"Vue RH"' in SOURCE
    assert "needs_employees" in SOURCE
    assert "get_employes() if needs_employees else pd.DataFrame()" in SOURCE
    assert "get_conges() if active_panel == noms_onglets[1]" in SOURCE
    assert "if can_read_paie:" in SOURCE
    calls = [n for n in ast.walk(page) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name) and n.func.id in (
                 "get_employes", "get_conges")]
    assert len(calls) == 2


def test_five_panels_render_without_unrelated_employee_or_leave_reads():
    run_isolated(r'''
from streamlit.testing.v1 import AppTest
source = """
import pandas as pd
import streamlit as st
from unittest.mock import patch
from modules.rh.views import show_rh_page

names = [
    '👨‍💼 Registre des Employés', '🌴 Gestion des Congés',
    '🧮 Simulation IRG (non validée)', '🔎 Préparation Paie IRG / CNAS',
    '🧪 Atelier paie fictive',
]

def get_emps():
    chosen = st.session_state.get('_erp_rh_active_panel', names[0])
    assert chosen in (names[0], names[1], names[4]), 'Lecture employés hors panneau'
    return pd.DataFrame(columns=['employe_id','nom','actif'])

def get_leaves():
    assert st.session_state.get('_erp_rh_active_panel') == names[1], 'Lecture congés hors panneau'
    return pd.DataFrame(columns=['demande_conge_id'])

with patch('modules.rh.views._rh_access', return_value=('ADMIN', True, True)), \\
     patch('modules.rh.views.get_employes', side_effect=get_emps), \\
     patch('modules.rh.views.get_conges', side_effect=get_leaves):
    show_rh_page()
"""
app = AppTest.from_string(source, default_timeout=30).run()
names = [
    '👨‍💼 Registre des Employés', '🌴 Gestion des Congés',
    '🧮 Simulation IRG (non validée)', '🔎 Préparation Paie IRG / CNAS',
    '🧪 Atelier paie fictive',
]
for label in names:
    if app.selectbox(key='_erp_rh_active_panel').value != label:
        app = app.selectbox(key='_erp_rh_active_panel').set_value(label).run()
    assert not app.exception, [x.message for x in app.exception]
    assert not app.tabs, 'Les anciens onglets exécutent tous les panneaux'
    assert app.selectbox(key='_erp_rh_active_panel').options == names
    assert not app.success, 'Aucune écriture n’est attendue dans ces consultations'
''')


def test_without_paie_permission_only_two_views_offered():
    run_isolated(r'''
from streamlit.testing.v1 import AppTest
source = """
import pandas as pd
from unittest.mock import patch
from modules.rh.views import show_rh_page
with patch('modules.rh.views._rh_access', return_value=('LECTEUR', False, False)), \\
     patch('modules.rh.views.get_employes',
           return_value=pd.DataFrame(columns=['employe_id','nom','actif'])), \\
     patch('modules.rh.views.get_conges',
           side_effect=AssertionError('Congés non sélectionnés')):
    show_rh_page()
"""
app = AppTest.from_string(source).run()
assert not app.exception, app.exception
options = app.selectbox(key='_erp_rh_active_panel').options
assert options == ['👨‍💼 Registre des Employés', '🌴 Gestion des Congés']
assert not app.button, 'Aucune commande de simulation Paie ne doit être visible'
''')


def test_rh_permission_failure_prevents_navigation_and_registry_reads():
    run_isolated(r'''
from streamlit.testing.v1 import AppTest
source = """
from unittest.mock import patch
from modules.rh.views import show_rh_page
with patch('modules.rh.views._rh_access', return_value=None), \\
     patch('modules.rh.views.get_employes',
           side_effect=AssertionError('Lecture interdite')), \\
     patch('modules.rh.views.get_conges',
           side_effect=AssertionError('Lecture interdite')):
    show_rh_page()
"""
app = AppTest.from_string(source).run()
assert not app.exception, app.exception
assert len(app.error) == 1
assert not app.selectbox
''')
