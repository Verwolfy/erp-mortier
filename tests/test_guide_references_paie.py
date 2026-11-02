"""Vérification du rendu et des sources du guide de paie."""
import subprocess
import sys
from pathlib import Path

def test_guide_paie_renders_with_sources_and_limits():
    script = '''
from streamlit.testing.v1 import AppTest
from modules.help.views import HELP_SECTIONS
app=AppTest.from_string("from modules.help.views import show_help_page"+chr(10)+"show_help_page()").run()
for name in HELP_SECTIONS:
    app.sidebar.radio[0].set_value(name).run()
    assert not app.exception, name
app.sidebar.radio[0].set_value("📚 Paie : règles et références").run()
body=" ".join(x.value for x in app.markdown)
for expected in ("joradp.dz/FTP/jo-francais/2015/F2015049.pdf","mfdgi.gov.dz/fr/particuliers/irg-traitements-et-salaires","dgb.mf.gov.dz/wp-content/uploads/2026/01/LF-2026.pdf","ne sont pas qualifiés","prime mensuelle de panier"):
    assert expected in body, expected
assert any("GUIDE-09" in x.value for x in app.caption)
'''
    r=subprocess.run([sys.executable,'-c',script],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=45)
    assert r.returncode==0,r.stdout+r.stderr
