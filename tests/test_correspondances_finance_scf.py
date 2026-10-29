"""Correspondances de comptes Finance/SCF : jamais d'écriture comptable."""
from types import SimpleNamespace
from unittest.mock import Mock
from copy import deepcopy
import pytest

from core.correspondances_finance_scf import (
    CorrespondanceSCFIndisponible,
    analyser_correspondances_finance_scf,
    lire_correspondances_finance_scf,
)


def finance():
    return [
        {"compte_id":"FIN-1","nom_compte":"Banque principale","type_compte":"Banque",
         "numero_compte":"512","statut":"OUI"},
        {"compte_id":"FIN-2","nom_compte":"Clients","type_compte":"Tiers client",
         "numero_compte":"411","statut":"OUI"},
        {"compte_id":"FIN-3","nom_compte":"Divers","type_compte":"Banque",
         "numero_compte":"5121","statut":"OUI"},
        {"compte_id":"FIN-4","nom_compte":"A qualifier","type_compte":"Banque",
         "numero_compte":None,"statut":"OUI"},
        {"compte_id":"FIN-5","nom_compte":"Fermé","type_compte":"Caisse",
         "numero_compte":"53","statut":"NON"},
    ]


def scf():
    return [
        {"numero_compte":"512","libelle":"Banques comptes courants","actif":False,"mouvementable":False},
        {"numero_compte":"411","libelle":"Clients","actif":True,"mouvementable":True},
        {"numero_compte":"53","libelle":"Caisse","actif":False,"mouvementable":False},
    ]


def test_correspondances_exactes_non_homologuees():
    result = analyser_correspondances_finance_scf(finance(), scf())
    assert result["nombre_comptes_finance"] == 5
    assert result["nombre_comptes_scf"] == 3
    assert result["repartition"] == {
        "SANS_NUMERO": 1, "NON_REFERENCE": 1,
        "REFERENCE_INACTIVE": 1, "CANDIDAT_A_VALIDER": 1,
        "COMPTE_FINANCE_INACTIF": 1,
    }
    assert result["ecritures_automatiques_autorisees"] is False
    by_id = {row["compte_finance_id"]: row for row in result["lignes"]}
    assert by_id["FIN-1"]["statut"] == "REFERENCE_INACTIVE"
    assert by_id["FIN-2"]["statut"] == "CANDIDAT_A_VALIDER"
    assert by_id["FIN-3"]["numero_scf_identique"] is None
    assert by_id["FIN-4"]["statut"] == "SANS_NUMERO"


@pytest.mark.parametrize("change", [
    lambda a,b: a.append(deepcopy(a[0])),
    lambda a,b: b.append(deepcopy(b[0])),
    lambda a,b: a[0].update(statut="INCONNU"),
    lambda a,b: a[0].update(numero_compte=512),
    lambda a,b: a[0].update(compte_id=None),
    lambda a,b: a[0].update(nom_compte=" "),
    lambda a,b: b[0].update(actif="NON"),
    lambda a,b: b[0].update(mouvementable=None),
    lambda a,b: b[0].update(numero_compte="5120X"),
    lambda a,b: b[0].update(libelle=None),
])
def test_refuse_sources_ambigues(change):
    a,b = finance(),scf()
    change(a,b)
    with pytest.raises(CorrespondanceSCFIndisponible):
        analyser_correspondances_finance_scf(a,b)


def test_aucun_compte_reste_non_autorise():
    result = analyser_correspondances_finance_scf([], scf())
    assert result["nombre_comptes_finance"] == 0
    assert not result["ecritures_automatiques_autorisees"]


def test_lecture_exhaustive_en_base():
    db = Mock()
    query = db.table.return_value.select.return_value.range.return_value
    query.execute.return_value = SimpleNamespace(data=scf(),count=3)
    r = lire_correspondances_finance_scf(finance(),db_client=db)
    assert r["nombre_comptes_scf"] == 3
    db.table.assert_called_once_with("scf_plan_comptes")
    assert db.table.return_value.select.call_args.kwargs["count"] == "exact"
    assert db.table.return_value.select.return_value.range.call_args.args == (0,999)


@pytest.mark.parametrize("count,data", [(None,[]),(3,[]),(1,scf()),(True,[])])
def test_lecture_tronquee_bloquee(count,data):
    db=Mock()
    db.table.return_value.select.return_value.range.return_value.execute.return_value=(
        SimpleNamespace(data=data,count=count)
    )
    with pytest.raises(CorrespondanceSCFIndisponible):
        lire_correspondances_finance_scf(finance(),db_client=db)


def test_reseau_indisponible_bloque_sans_fuite():
    db=Mock()
    db.table.side_effect=TimeoutError("Secret interne")
    with pytest.raises(CorrespondanceSCFIndisponible,match="Plan SCF inaccessible"):
        lire_correspondances_finance_scf(finance(),db_client=db)


def test_service_serveur_obligatoire():
    with pytest.raises(CorrespondanceSCFIndisponible):
        lire_correspondances_finance_scf(finance(),db_client=None)
