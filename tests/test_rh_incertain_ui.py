"""Simulation locale du résultat incertain, aucun accès base."""
import subprocess
import sys
from pathlib import Path

def test_conge_uncertain_shows_warning_without_success():
    script = '''
import pandas as pd
from streamlit.testing.v1 import AppTest
source="""
import pandas as pd
from unittest.mock import patch
from modules.rh.views import show_rh_page
rows=pd.DataFrame([{'employe_id':'SIM-RH-001','nom':'[FICTIF] Test','actif':'OUI'}])
conges=pd.DataFrame([{'demande_conge_id':'SIM-CNG-001'}])
with patch('modules.rh.views._rh_access',return_value=('ADMIN',True,False)), patch('modules.rh.views.get_employes',return_value=rows), patch('modules.rh.views.get_conges',return_value=conges), patch('modules.rh.views.create_demande_conge',side_effect=RuntimeError('secret-ne-pas-afficher')):
    show_rh_page()
"""
app=AppTest.from_string(source).run()
assert not app.exception
assert any('SIM-CNG' in w.value for w in app.warning)
app.button(key='FormSubmitter:form_conges-Soumettre la demande').click().run()
assert not app.exception
assert any('registre avant de recommencer' in e.value for e in app.error)
assert not app.success
assert not any('secret-ne-pas-afficher' in e.value for e in app.error)
'''
    r=subprocess.run([sys.executable,'-c',script],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=45)
    assert r.returncode==0,r.stdout+r.stderr
