"""Simulations arithmétiques fictives hors ligne, sans valeur juridique."""
import json
from pathlib import Path
from decimal import Decimal
from core.paie_preparation import preparer_bulletin_paie


def test_huit_bulletins_de_simulation_et_controles():
    rows=json.loads((Path(__file__).parent/'fixtures/rh_simulation_employes.json').read_text())
    def param(code, value):
        return dict(code=code,valeur=value,unite='fraction',date_effet='2026-01-01',date_fin=None,statut_juridique='en_vigueur',niveau_confiance='CONFIRMEE',source='SOURCE_FICTIVE_TEST',date_verification='2026-01-03')
    for i, row in enumerate((x for x in rows if x['actif']=='OUI'),start=1):
        base=Decimal('40000')+Decimal(i)*1000
        result=preparer_bulletin_paie(employe_id=row['employe_id'],date_paie='2026-11-30',salaire_base=str(base),primes='0',assiette_cnas=str(base),assiette_irg=str(base),montant_irg='1000',preuve_irg={'statut':'CONFIRMEE','source':'TEST_FICTIF','code':'IRG-TEST','date_paie':'2026-11-30'},autres_retenues='0',parametres=[param('CNAS_SALARIE_TAUX','0.05'),param('CNAS_EMPLOYEUR_TAUX','0.10')])
        assert result['statut']=='SIMULATION_NON_VALIDEE'
        assert Decimal(result['net_a_payer'])==base-(base*Decimal('0.05'))-Decimal('1000')
        assert result['tracabilite']['irg']=='TEST_FICTIF'
    assert i==8
