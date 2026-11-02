"""Comparaison documentaire bornée, aucun appel de données ou d'écriture."""
from decimal import Decimal
import pytest
from core.simulation_paie_dgi import comparaison_dgi_2022

@pytest.mark.parametrize('ident,brut,assiette,irg,net',[
 ('SIM-RH-001','41000','37310','2481.30','34828.70'),
 ('SIM-RH-002','42000','38220','2690.60','35529.40'),
 ('SIM-RH-003','43000','39130','2899.90','36230.10'),
 ('SIM-RH-004','44000','40040','3110.80','36929.20'),
 ('SIM-RH-005','45000','40950','3356.50','37593.50'),
 ('SIM-RH-006','46000','41860','3602.20','38257.80'),
 ('SIM-RH-007','47000','42770','3847.90','38922.10'),
 ('SIM-RH-008','48000','43680','4093.60','39586.40'),
])
def test_exemples_documentaires(ident,brut,assiette,irg,net):
    r=comparaison_dgi_2022(ident)
    assert [r[k] for k in ('brut','assiette_irg','irg_table','net')]==list(map(Decimal,(brut,assiette,irg,net)))
    assert r['cotisation_salarie']==Decimal(brut)*Decimal('.09')
    assert r['cotisation_employeur']==Decimal(brut)*Decimal('.25')

@pytest.mark.parametrize('ident',['EMP-0001','SIM-RH-009','SIM-RH-000','autre'])
def test_identifiant_hors_jeu_refuse(ident):
    with pytest.raises(ValueError): comparaison_dgi_2022(ident)
