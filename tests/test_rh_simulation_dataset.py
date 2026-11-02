"""Jeu fictif durable et rendu RH sans connexion ni écriture réelle."""
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
from core.utils import generate_unique_id
from modules.dashboards.service import get_kpis_rh

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'tests/fixtures/rh_simulation_employes.json'


def test_simulation_hierarchy_counts_and_real_id_sequence():
    rows=json.loads(FIXTURE.read_text())
    ids={r['employe_id'] for r in rows}
    assert len(rows)==len(ids)==10
    assert all(r['nom'].startswith('[FICTIF]') for r in rows)
    assert all(r['manager_id'] is None or r['manager_id'] in ids for r in rows)
    assert generate_unique_id('EMP',list(ids))=='EMP-0001'
    with patch('modules.dashboards.service.fetch_data',side_effect=lambda t:rows if t=='employes' else []):
        k=get_kpis_rh(None,None)
    assert k['effectif_actif']==8
    assert k['repartition_service']['Effectif'].sum()==8
    assert len(k['repartition_service'])==6


def test_real_streamlit_forms_use_only_active_simulated_employees():
    script='''
import json
from pathlib import Path
from streamlit.testing.v1 import AppTest
source="""
import json
from pathlib import Path
from unittest.mock import patch
import pandas as pd
import streamlit as st
from modules.rh.views import show_rh_page
rows=json.loads(Path('tests/fixtures/rh_simulation_employes.json').read_text())
if st.session_state.get('all_inactive'):
    for row in rows: row['actif']='NON'
with patch('modules.rh.views._rh_access',return_value=('ADMIN',True,False)), patch('modules.rh.views.get_employes',return_value=pd.DataFrame(rows)), patch('modules.rh.views.get_conges',return_value=pd.DataFrame()), patch('modules.rh.views.create_employe',side_effect=AssertionError('unexpected write')), patch('modules.rh.views.create_demande_conge',side_effect=AssertionError('unexpected write')):
    show_rh_page()
"""
app=AppTest.from_string(source).run()
assert not app.exception
assert any('10 fiche(s) SIM-RH' in w.value for w in app.warning)
employees=[s for s in app.selectbox if s.label=='Employé']
assert len(employees)==1 and len(employees[0].options)==8
assert not any('009' in o or '010' in o for o in employees[0].options)
app.session_state['all_inactive']=True
app.run()
assert not app.exception
assert not [s for s in app.selectbox if s.label=='Employé']
assert not [b for b in app.button if b.label=='Soumettre la demande']
assert any('Aucun employé actif' in w.value for w in app.warning)
'''
    result=subprocess.run([sys.executable,'-c',script],cwd=ROOT,capture_output=True,text=True,timeout=45)
    assert result.returncode==0,result.stdout+result.stderr
