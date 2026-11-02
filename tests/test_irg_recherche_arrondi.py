"""Expérience hors ligne : quatre lignes de la table DGI 2022, non qualification."""
import subprocess
import sys
from pathlib import Path

def test_arrondi_experimental_compare_quatre_lignes_dgi():
    script = """
from decimal import Decimal, ROUND_HALF_UP
import runpy
m=runpy.run_path('tests/test_irg_salaires.py')
cas=[('33000','1328.60'),('35000','2070.00'),('35010','2071.40'),('50000','5800.00')]
for base, attendu in cas:
    resultat=Decimal(m['run'](base, 'SALARIE')['irg_simule'])
    candidat=resultat.quantize(Decimal('0.1'),rounding=ROUND_HALF_UP)
    assert candidat == Decimal(attendu), (base, candidat, attendu)
"""
    r=subprocess.run([sys.executable,'-c',script],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=45)
    assert r.returncode==0,r.stdout+r.stderr
