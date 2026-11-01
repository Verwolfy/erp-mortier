"""Rendu Streamlit hors ligne : panne isolée, jamais de faux succès ou faux zéro."""
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _run(script):
    # Les suites historiques installent des doubles de Streamlit dans sys.modules.
    # Un processus isolé permet ici d'exercer le vrai moteur de rendu Streamlit.
    result = subprocess.run([sys.executable, '-c', script], cwd=ROOT,
                            capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr


def test_dashboard_failed_sales_read_does_not_show_zero_ca():
    _run('''
from streamlit.testing.v1 import AppTest
app = AppTest.from_string("""
from unittest.mock import patch
import streamlit as st
from core.strict_reads import DataReadError
from modules.dashboards.views import show_dashboards_page
st.session_state['user'] = {'role':'ADMIN'}
def read(table, *args, **kwargs):
    if table == 'factures':
        raise DataReadError('private-data-sentinel')
    return []
with patch('modules.dashboards.views.has_permission', return_value=True), \\
     patch('modules.dashboards.service.fetch_data', side_effect=read), \\
     patch('modules.dashboards.service.fetch_data_by_date_range', side_effect=read):
    show_dashboards_page()
""").run(timeout=20)
assert not app.exception, app.exception
assert len(app.error) == 3, [e.value for e in app.error]
assert all('private-data-sentinel' not in e.value for e in app.error)
assert not [m for m in app.metric if m.label.startswith(('CA ', 'Chiffre', 'Facturation brute'))]
assert any(m.label == 'Effectif Actif' for m in app.metric)
''')


def test_crm_failed_lists_show_unavailable_but_nextgen_remains_disabled():
    _run('''
from streamlit.testing.v1 import AppTest
app = AppTest.from_string("""
from unittest.mock import patch
import streamlit as st
from core.strict_reads import DataReadError
from modules.crm.views import show_crm_page
st.session_state['user'] = {'role':'ADMIN'}
with patch('modules.crm.views.has_permission', return_value=False), \\
     patch('modules.crm.views.get_pipeline', side_effect=DataReadError('private-data-sentinel')), \\
     patch('modules.crm.views.get_clients_actifs', side_effect=DataReadError('private-data-sentinel')), \\
     patch('modules.crm.views.get_interactions', side_effect=DataReadError('private-data-sentinel')), \\
     patch('modules.crm.views.inbox_enabled', return_value=False):
    show_crm_page()
""").run(timeout=20)
assert not app.exception, app.exception
assert len(app.error) == 3
assert not app.success
assert all('private-data-sentinel' not in e.value for e in app.error)
assert not any('Aucune opportunité' in e.value or 'Aucun historique' in e.value for e in app.info)
assert any('confidentialité' in e.value for e in app.info)
''')


def test_dashboard_empty_sales_renders_zero_without_exception():
    _run('''
from streamlit.testing.v1 import AppTest
app = AppTest.from_string("""
from unittest.mock import patch
import streamlit as st
from modules.dashboards.views import show_dashboards_page
st.session_state['user'] = {'role':'ADMIN'}
with patch('modules.dashboards.views.has_permission', return_value=True), \\
     patch('modules.dashboards.service.fetch_data', return_value=[]), \\
     patch('modules.dashboards.service.fetch_data_by_date_range', return_value=[]):
    show_dashboards_page()
""").run(timeout=20)
assert not app.exception, app.exception
assert not app.error, app.error
assert any(m.label == 'Facturation brute TTC' and m.value == '0.00 DZD' for m in app.metric)
assert any('KPI-03' in c.value for c in app.caption)
''')
