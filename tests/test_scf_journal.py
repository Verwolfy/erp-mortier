"""Tests fonctionnels du socle SCF, comptes d'exemple non officiels."""
from decimal import Decimal
import pytest
from core.scf_journal import EcritureSCFInvalide, preparer_ecriture_scf, calculer_balance_scf


def exemple(**change):
    data=dict(date_ecriture="2026-10-28", journal="VE", reference="FAC-TEST-001",
              libelle="Vente fictive", periode={"statut":"OUVERTE", "date_debut":"2026-01-01",
              "date_fin":"2026-12-31"}, comptes={"411001":{"actif":True,"mouvementable":True},
              "701001":{"actif":True,"mouvementable":True}},
              lignes=[{"compte":"411001","debit":"119.00","credit":"0"},
                      {"compte":"701001","debit":"0","credit":"119.00"}])
    data.update(change)
    return data


def test_piece_equilibree():
    result=preparer_ecriture_scf(**exemple())
    assert result["total_debit"]=="119.00"
    assert result["total_credit"]=="119.00"
    assert result["statut"]=="PREPAREE"
    assert result["devise"]=="DZD"


def test_balance_comptable():
    piece=preparer_ecriture_scf(**exemple())
    piece["statut"]="VALIDEE"
    balance=calculer_balance_scf([piece])
    assert Decimal(balance["411001"]["solde"]) == Decimal("119.00")
    assert Decimal(balance["701001"]["solde"]) == Decimal("-119.00")
    assert sum(Decimal(v["solde"]) for v in balance.values())==0


@pytest.mark.parametrize("modification",[
    {"date_ecriture":"2027-01-01"},
    {"date_ecriture":"2026-02-30"},
    {"periode":{"statut":"CLOTUREE","date_debut":"2026-01-01","date_fin":"2026-12-31"}},
    {"journal":""},
    {"reference":""},
    {"lignes":[]},
    {"lignes":[{"compte":"411001","debit":"1","credit":"0"}]},
    {"lignes":[{"compte":"411001","debit":"120","credit":"0"},
               {"compte":"701001","debit":"0","credit":"119"}]},
    {"lignes":[{"compte":"411001","debit":"0","credit":"0"},
               {"compte":"701001","debit":"0","credit":"0"}]},
    {"lignes":[{"compte":"411001","debit":"1","credit":"1"},
               {"compte":"701001","debit":"0","credit":"1"}]},
    {"lignes":[{"compte":"411001","debit":"1.001","credit":"0"},
               {"compte":"701001","debit":"0","credit":"1.001"}]},
    {"lignes":[{"compte":"911001","debit":"1","credit":"0"},
               {"compte":"701001","debit":"0","credit":"1"}]},
    {"lignes":[{"compte":"411001","debit":True,"credit":"0"},
               {"compte":"701001","debit":"0","credit":"1"}]},
    {"comptes":{"411001":{"actif":False,"mouvementable":True},
                 "701001":{"actif":True,"mouvementable":True}}},
])
def test_ecritures_invalides(modification):
    with pytest.raises(EcritureSCFInvalide):
        preparer_ecriture_scf(**exemple(**modification))


def test_balance_refuse_brouillon():
    with pytest.raises(EcritureSCFInvalide):
        calculer_balance_scf([preparer_ecriture_scf(**exemple())])


def test_balance_refuse_piece_desiquilibree():
    piece=preparer_ecriture_scf(**exemple())
    piece["statut"]="VALIDEE"
    piece["lignes"][1]["credit"]="118"
    with pytest.raises(EcritureSCFInvalide):
        calculer_balance_scf([piece])
