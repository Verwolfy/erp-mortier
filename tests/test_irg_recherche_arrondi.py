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

def test_essai_double_arrondi_32000_differe_de_la_table_dgi():
    """L'essai en deux arrondis ne reproduit pas la ligne DGI à 32 000 DA."""
    from decimal import Decimal, ROUND_HALF_UP
    # Formule DGI du cas général après premier abattement : 1656 DA.
    montant = Decimal(1656) * Decimal(137) / Decimal(51) - Decimal(27925) / Decimal(8)
    direct = montant.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
    double = montant.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP).quantize(
        Decimal('0.1'), rounding=ROUND_HALF_UP
    )
    assert direct == Decimal('957.80')  # table DGI 2022, assiette 32 000
    assert double == Decimal('957.90')
