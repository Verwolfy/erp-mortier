"""Tests pour brouillon interne : aucun formulaire officiel simulé."""
from decimal import Decimal
import pytest
from core.declarations_fiscales import DeclarationNonDisponible, preparer_tva_periodique


def piece(**updates):
    p=dict(piece_id="DOC-A",statut="VALIDE",nature_tva="COLLECTEE",
           classification_verifiee=True,source_juridique="SOURCE_FICTIVE_TEST",
           date_fait_generateur="2026-10-15",montant_tva="190")
    p.update(updates)
    return p


def test_collectee_deductible_et_credit():
    result=preparer_tva_periodique(
        annee=2026,mois=10,pieces=[
            piece(),piece(piece_id="DOC-B",nature_tva="DEDUCTIBLE",montant_tva="40")
        ],credit_anterieur="10",
    )
    assert result["tva_collectee"]=="190"
    assert result["tva_deductible"]=="40"
    assert result["tva_a_payer"]=="140"
    assert result["credit_a_reporter"]=="0"
    assert result["statut"]=="BROUILLON_INTERNE_NON_DEPOSABLE"


def test_credit_a_reporter():
    r=preparer_tva_periodique(
        annee=2026,mois=10,pieces=[
            piece(montant_tva="10"),piece(piece_id="D2",nature_tva="DEDUCTIBLE",montant_tva="20")
        ],credit_anterieur="5")
    assert Decimal(r["tva_a_payer"]) == 0
    assert Decimal(r["credit_a_reporter"]) == 15


@pytest.mark.parametrize("changes",[
    {"statut":"BROUILLON"}, {"classification_verifiee":False},
    {"source_juridique":""}, {"date_fait_generateur":"2026-09-30"},
    {"date_fait_generateur":"2026-02-30"}, {"nature_tva":"EXONEREE"},
    {"montant_tva":"NaN"}, {"montant_tva":"1.111"},
    {"montant_tva":-1}, {"piece_id":""},
])
def test_piece_invalide_bloquee(changes):
    with pytest.raises(DeclarationNonDisponible):
        preparer_tva_periodique(annee=2026,mois=10,pieces=[piece(**changes)])


def test_pas_de_doublons():
    with pytest.raises(DeclarationNonDisponible):
        preparer_tva_periodique(annee=2026,mois=10,pieces=[piece(),piece()])


@pytest.mark.parametrize("annee,mois",[(True,10),(2026,False),(1999,1),(2026,13)])
def test_mauvaise_periode(annee,mois):
    with pytest.raises(DeclarationNonDisponible):
        preparer_tva_periodique(annee=annee,mois=mois,pieces=[])


def test_rien_a_declarer_en_interne():
    r=preparer_tva_periodique(annee=2026,mois=10,pieces=[])
    assert r["tva_a_payer"]=="0"
    assert r["credit_a_reporter"]=="0"
