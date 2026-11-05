"""Contrôles exports sans données personnelles ni pièces réelles."""
import csv
import io

import pytest
from core.export_scf import ExportRefuse, exporter_journal_scf_csv


def piece(**updates):
    p=dict(
      statut="VALIDEE",date_ecriture="2026-10-28",journal="VE",
      reference="REF-001",libelle="Écriture de test",
      lignes=[{"compte":"411001","debit":"10.00","credit":"0"},
              {"compte":"701001","debit":"0","credit":"10.00"}],
    )
    p.update(updates)
    return p


def test_csv_utf8_et_ordre():
    content=exporter_journal_scf_csv([piece()],droit_export=True)
    rows=list(csv.reader(io.StringIO(content),delimiter=";"))
    assert len(rows)==3
    assert rows[1][0]=="2026-10-28"
    assert rows[1][4]=="10.00"
    assert rows[2][5]=="10.00"


def test_csv_formule_ne_s_execute_pas():
    content=exporter_journal_scf_csv([piece(libelle=" =1+1")],droit_export=True)
    rows=list(csv.reader(io.StringIO(content),delimiter=";"))
    assert rows[1][-1].startswith("'")
    assert "=1+1" in rows[1][-1]


def test_export_refuse_si_non_autorise():
    with pytest.raises(PermissionError):
        exporter_journal_scf_csv([piece()],droit_export=False)


@pytest.mark.parametrize("change",[
    {"statut":"BROUILLON"},
    {"statut":"PREPAREE"},
    {"libelle":"x"*501},
    {"lignes":[{"compte":"411001","debit":"10.00","credit":"0"},
               {"compte":"701001","debit":"0","credit":"9.00"}]},
    {"lignes":[]},
])
def test_refus_donnees_invalides(change):
    with pytest.raises(ExportRefuse):
        exporter_journal_scf_csv([piece(**change)],droit_export=True)


@pytest.mark.parametrize("updates", [
    {"reference": "DEMO26_SCFPIECE"},
    {"reference": " demo26_scfpiece "},
    {"journal": "DEMO26_JRN"},
    {"lignes": [
        {"compte": "41199926", "debit": "10.00", "credit": "0"},
        {"compte": "701001", "debit": "0", "credit": "10.00"},
    ]},
    {"lignes": [
        {"compte": "411001", "debit": "10.00", "credit": "0"},
        {"compte": "70199926", "debit": "0", "credit": "10.00"},
    ]},
])
def test_export_scf_refuse_les_pieces_fictives_meme_validees(updates):
    with pytest.raises(ExportRefuse):
        exporter_journal_scf_csv([piece(**updates)], droit_export=True)


def test_export_scf_normal_reste_possible():
    assert len(list(csv.reader(
        io.StringIO(exporter_journal_scf_csv([piece()], droit_export=True)),
        delimiter=";"
    ))) == 3
