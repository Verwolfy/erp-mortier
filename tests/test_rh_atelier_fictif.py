"""Atelier fictif : permissions existantes, sélection bornée, aucune écriture."""
import subprocess
import sys
from pathlib import Path

def test_atelier_simule_sans_ecriture():
    script = """
from streamlit.testing.v1 import AppTest
source = '''
from unittest.mock import patch
import pandas as pd
from modules.rh.views import show_rh_page
data=pd.DataFrame([
 {'employe_id':'SIM-RH-001','nom':'[FICTIF] Simulation 001','actif':'OUI'},
 {'employe_id':'SIM-RH-009','nom':'[FICTIF] Simulation 009','actif':'NON'},
 {'employe_id':'EMP-0001','nom':'Salarié réel','actif':'OUI'},
 {'employe_id':'SIM-RH-002','nom':'Nom sans marqueur','actif':'OUI'}])
with patch('modules.rh.views._rh_access',return_value=('ADMIN',True,True)), patch('modules.rh.views.get_employes',return_value=data), patch('modules.rh.views.get_conges',return_value=pd.DataFrame()), patch('modules.rh.views.create_employe',side_effect=AssertionError('écriture interdite')), patch('modules.rh.views.create_demande_conge',side_effect=AssertionError('écriture interdite')):
    show_rh_page()
'''
app=AppTest.from_string(source).run()
assert not app.exception, app.exception
selector=app.selectbox(key='rh_test_employe')
assert selector.options==['SIM-RH-001'],selector.options
app.button(key='rh_test_calculer').click().run()
assert not app.exception, app.exception
metrics={m.label:m.value for m in app.metric}
assert metrics['Base fictive (DZD)']=='41000.00'
assert metrics['Net fictif (DZD)']=='37950.00'
assert any('aucun calcul CNAS ou IRG officiel' in w.value for w in app.warning)
assert not app.success
"""
    r=subprocess.run([sys.executable,'-c',script],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=45)
    assert r.returncode==0,r.stdout+r.stderr
