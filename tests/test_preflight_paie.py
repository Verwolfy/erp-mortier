"""Préparation IRG/CNAS avec données synthétiques, aucune lecture salarié."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from core.preflight_paie import (
    PreparationPaieIndisponible, lire_preparation_paie, verifier_referentiels_paie,
)


def param(code, value):
    return {
        "code": code, "valeur": value, "unite": "fraction",
        "date_effet": "2026-01-01", "date_fin": None,
        "statut_juridique": "en_vigueur",
        "niveau_confiance": "CONFIRMEE",
        "source": "SOURCE_FICTIVE_TEST", "date_verification": "2026-01-02",
    }


def irg():
    return {
        "code": "IRG_SALAIRES_MENSUEL", "type_regle": "progressif",
        "date_effet": "2026-01-01", "date_fin": None,
        "statut_juridique": "en_vigueur",
        "niveau_confiance": "CONFIRMEE",
        "source": "SOURCE_FICTIVE_TEST", "date_verification": "2026-01-02",
        "donnees": {"tranches": [
            {"jusqua": "10000", "taux": "0"},
            {"jusqua": None, "taux": "0.1"},
        ]},
    }


def test_aucune_regle_ne_declenche_pas_de_bulletin():
    result=verifier_referentiels_paie([], [], "2026-10-29")
    assert result["reference_cnas_salarie"] is False
    assert result["reference_cnas_employeur"] is False
    assert result["reference_irg_mensuel"] is False
    assert result["bulletin_officiel_autorise"] is False
    assert result["declaration_sociale_autorisee"] is False
    assert result["qualification_assiette_individuelle"] == "NON_VERIFIEE"


def test_regles_synthetiques_ne_creent_pas_droits_emission():
    params = [param("CNAS_SALARIE_TAUX","0.05"),
              param("CNAS_EMPLOYEUR_TAUX","0.15")]
    result=verifier_referentiels_paie(params,[irg()],"2026-10-29")
    assert result["reference_cnas_salarie"]
    assert result["reference_cnas_employeur"]
    assert result["reference_irg_mensuel"]
    assert result["bulletin_officiel_autorise"] is False


def test_regle_expiree_n_est_pas_utilisee():
    p=param("CNAS_SALARIE_TAUX","0.1")
    p["date_fin"]="2026-02-01"
    r=verifier_referentiels_paie([p],[],"2026-10-29")
    assert not r["reference_cnas_salarie"]


@pytest.mark.parametrize("params", [
    [param("CNAS_SALARIE_TAUX", "1.1")],
    [param("CNAS_SALARIE_TAUX", "-0.1")],
    [param("CNAS_SALARIE_TAUX", "NaN")],
    [param("CNAS_SALARIE_TAUX", "0.1"), param("CNAS_SALARIE_TAUX", "0.2")],
    [param("CNAS_SALARIE_TAUX", "0.1") | {"source": None}],
])
def test_regle_sociale_non_valide_bloque(params):
    with pytest.raises(PreparationPaieIndisponible):
        verifier_referentiels_paie(params,[],"2026-10-29")


@pytest.mark.parametrize("rulechange", [
    {"type_regle":"autre"},
    {"donnees":{}},
    {"donnees":{"tranches":[]}},
    {"source":None},
])
def test_configuration_irg_ambigue_ou_incomplete(rulechange):
    r=irg()
    r.update(rulechange)
    with pytest.raises(PreparationPaieIndisponible):
        verifier_referentiels_paie([], [r], "2026-10-29")


@pytest.mark.parametrize("datevalue", ["2026-99-99","29-10-2026","2026-10-1", None])
def test_date_rejetee(datevalue):
    with pytest.raises(PreparationPaieIndisponible):
        verifier_referentiels_paie([], [], datevalue)


def test_lecture_du_registre_sans_employe():
    db=MagicMock()
    q=db.table.return_value
    q.select.return_value=q
    q.in_.return_value=q
    q.eq.return_value=q
    q.order.return_value=q
    q.range.return_value=q
    q.execute.side_effect=[
        SimpleNamespace(data=[],count=0),
        SimpleNamespace(data=[],count=0),
    ]
    r=lire_preparation_paie(db_client=db,date_paie="2026-10-29")
    assert r["statut"]=="PREPARATION_A_COMPLETER"
    assert [c.args[0] for c in db.table.call_args_list]==[
        "parametres_reglementaires", "regles_reglementaires"
    ]
    assert q.insert.call_count==0
    assert q.update.call_count==0


@pytest.mark.parametrize("rows,count", [([],True),([],1),([{}],0),("bad",3)])
def test_lecture_paginee_bloquee(rows,count):
    db=MagicMock()
    q=db.table.return_value
    q.select.return_value=q
    q.in_.return_value=q
    q.order.return_value=q
    q.range.return_value=q
    q.execute.return_value=SimpleNamespace(data=rows,count=count)
    with pytest.raises(PreparationPaieIndisponible):
        lire_preparation_paie(db_client=db,date_paie="2026-10-29")
