"""Tests de paie avec taux FICTIFS, aucune retenue légale effective."""
from decimal import Decimal

import pytest

from core.paie_preparation import PaieNonDisponible, preparer_bulletin_paie


def param(code, valeur, **mod):
    p=dict(code=code,valeur=valeur,date_effet="2026-01-01",date_fin=None,
           statut_juridique="en_vigueur",niveau_confiance="CONFIRMEE",
           source="SOURCE_FICTIVE_TEST",date_verification="2026-01-03")
    p.update(mod)
    return p


def cas(**change):
    p=dict(
        employe_id="EMP-FICTIF",date_paie="2026-10-28",salaire_base="90000",
        primes="10000",assiette_cnas="100000",assiette_irg="91000",
        montant_irg="10000",preuve_irg={
            "statut":"CONFIRMEE","source":"TEST_FICTIF","code":"IRG-TEST",
            "date_paie":"2026-10-28",
        },autres_retenues="0",parametres=[
            param("CNAS_SALARIE_TAUX","0.09"),
            param("CNAS_EMPLOYEUR_TAUX","0.26"),
        ])
    p.update(change)
    return p


def test_net_brut_cotisations():
    result=preparer_bulletin_paie(**cas())
    assert result["brut"]=="100000"
    assert result["cnas_salarie"]=="9000.00"
    assert result["cnas_employeur"]=="26000.00"
    assert result["irg"]=="10000"
    assert result["net_a_payer"]=="81000.00"
    assert result["cout_employeur"]=="126000.00"
    assert result["statut"]=="SIMULATION_NON_VALIDEE"
    assert result["tracabilite"]["irg"]=="TEST_FICTIF"


@pytest.mark.parametrize("changes",[
    {"montant_irg":"NaN"}, {"montant_irg":-1}, {"primes":True},
    {"assiette_cnas":"150000"}, {"assiette_irg":"100001"},
    {"montant_irg":"95000"}, {"date_paie":"2026-13-01"},
    {"employe_id":""}, {"autres_retenues":"100000"},
    {"salaire_base":"0.001"},
    {"preuve_irg":{}},
    {"preuve_irg":{"statut":"NON_VERIFIEE","source":"TEST","code":"I","date_paie":"2026-10-28"}},
    {"preuve_irg":{"statut":"CONFIRMEE","source":"","code":"I","date_paie":"2026-10-28"}},
    {"preuve_irg":{"statut":"CONFIRMEE","source":"TEST","code":"I","date_paie":"2026-01-01"}},
    {"parametres":[]},
    {"parametres":[param("CNAS_SALARIE_TAUX","0.09")]},
    {"parametres":[param("CNAS_SALARIE_TAUX","1.5"),param("CNAS_EMPLOYEUR_TAUX","0.26")]},
    {"parametres":[param("CNAS_SALARIE_TAUX","0.09",statut_juridique="a_confirmer"),
                   param("CNAS_EMPLOYEUR_TAUX","0.26")]},
])
def test_erreurs_bloquantes(changes):
    with pytest.raises(PaieNonDisponible):
        preparer_bulletin_paie(**cas(**changes))


def test_changement_date_effet():
    params=[
        param("CNAS_SALARIE_TAUX","0.01",date_fin="2026-06-30"),
        param("CNAS_SALARIE_TAUX","0.09",date_effet="2026-07-01"),
        param("CNAS_EMPLOYEUR_TAUX","0.26"),
    ]
    v=preparer_bulletin_paie(**cas(parametres=params))
    assert Decimal(v["cnas_salarie"]) == Decimal("9000")


def test_produit_des_proofs_differentes():
    v=preparer_bulletin_paie(**cas())
    assert v["tracabilite"]["version_cnas_salarie"] == "2026-01-01"
    assert v["tracabilite"]["code_irg"] == "IRG-TEST"
