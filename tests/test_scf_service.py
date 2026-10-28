"""Tests lecture seule SCF avec données fictives et API Supabase simulée."""
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest

from core.scf_service import LectureSCFIndisponible, lire_balance_scf

PID = "00000000-0000-4000-8000-000000000001"


def piece(**kw):
    value = {
        "piece_id": PID, "statut": "VALIDEE", "date_ecriture": "2026-10-28",
        "code_journal": "VE", "reference": "FAC-FICTIVE",
        "libelle": "Exemple de vente sans TVA",
    }
    value.update(kw)
    return value


def ligne(n, compte, debit, credit, **kw):
    value = {
        "ligne_id": n, "piece_id": PID, "numero": n,
        "compte": compte, "debit": debit, "credit": credit,
    }
    value.update(kw)
    return value


def client(pieces=None, lignes=None, total_pieces=None, total_lignes=None):
    pieces = [piece()] if pieces is None else pieces
    lignes = [ligne(1, "411001", 100, 0),
              ligne(2, "701001", 0, 100)] if lignes is None else lignes
    p = MagicMock()
    l = MagicMock()
    for query in (p, l):
        query.select.return_value = query
        query.eq.return_value = query
        query.in_.return_value = query
        query.order.return_value = query
        query.range.return_value = query
    p.execute.return_value = SimpleNamespace(
        data=pieces, count=len(pieces) if total_pieces is None else total_pieces
    )
    l.execute.return_value = SimpleNamespace(
        data=lignes, count=len(lignes) if total_lignes is None else total_lignes
    )
    db = MagicMock()
    db.table.side_effect = lambda name: {
        "scf_pieces": p, "scf_lignes": l
    }[name]
    return db, p, l


def test_balance_validee_completement():
    db,p,l = client()
    data=lire_balance_scf(autorisation_serveur=True,db_client=db)
    assert data["pieces"] == 1
    assert data["lignes"] == 2
    assert data["balance"]["411001"]["solde"] == "100"
    assert data["balance"]["701001"]["solde"] == "-100"
    p.eq.assert_called_once_with("statut","VALIDEE")
    l.in_.assert_called_once_with("piece_id",[PID])
    db.table.assert_any_call("scf_pieces")
    db.table.assert_any_call("scf_lignes")
    assert p.insert.call_count == 0 and l.update.call_count == 0


def test_accès_refusé_avant_toute_lecture():
    db,_,_=client()
    with pytest.raises(PermissionError):
        lire_balance_scf(autorisation_serveur=False,db_client=db)
    db.table.assert_not_called()


def test_aucune_piece_validee():
    db,_,l=client(pieces=[])
    assert lire_balance_scf(autorisation_serveur=True,db_client=db) == {
        "pieces": 0, "lignes": 0, "balance": {},
    }
    l.execute.assert_not_called()


@pytest.mark.parametrize("changes", [
    {"total_pieces": 2}, {"total_lignes": 3},
    {"lignes": []}, {"lignes":[ligne(1,"411001",100,0)]},
    {"lignes":[ligne(1,"411001",100,0),ligne(2,"701001",0,90)]},
    {"lignes":[ligne(1,"411001",100,0),ligne(1,"701001",0,100)]},
    {"lignes":[ligne(1,"411001",100,0, piece_id="00000000-0000-4000-8000-000000000009")]},
    {"pieces":[piece(statut="BROUILLON")]},
    {"pieces":[piece(piece_id="malformed")]},
])
def test_donnees_incompletes_ou_incoherentes_refusees(changes):
    db,_,_=client(**changes)
    with pytest.raises(LectureSCFIndisponible):
        lire_balance_scf(autorisation_serveur=True,db_client=db)


def test_erreur_sql_sans_exposition():
    db,p,_=client()
    p.execute.side_effect=RuntimeError("TOKEN_DO_NOT_SHOW")
    with pytest.raises(LectureSCFIndisponible) as err:
        lire_balance_scf(autorisation_serveur=True,db_client=db)
    assert "TOKEN_DO_NOT_SHOW" not in str(err.value)
