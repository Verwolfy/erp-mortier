"""Tests de lecture seule avec client Supabase simulé."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from core.irg_salaires import IRGNonDisponible
from core.irg_service import simuler_irg_depuis_supabase
from tests.test_irg_salaires import bar


def client(rows=None, count=None):
    rows = [bar()] if rows is None else rows
    query=MagicMock()
    query.select.return_value=query
    query.eq.return_value=query
    query.order.return_value=query
    query.range.return_value=query
    query.execute.return_value=SimpleNamespace(
        data=rows, count=len(rows) if count is None else count,
    )
    db=MagicMock()
    db.table.return_value=query
    return db,query


def test_irg_computation_lecture_seule():
    db,q=client()
    result=simuler_irg_depuis_supabase(
        "50000","2026-10-28","SALARIE",db_client=db,
    )
    assert result["irg_simule"]=="5800.00"
    assert result["statut"]=="SIMULATION_NON_VALIDEE"
    db.table.assert_called_once_with("regles_reglementaires")
    q.eq.assert_called_once_with("code","IRG_SALAIRES_MENSUEL")
    q.range.assert_called_once_with(0,999)
    assert q.update.call_count==0 and q.insert.call_count==0


@pytest.mark.parametrize("rows,count",[
    ([],None),([bar()],2),([bar(),bar()],None),
])
def test_referentiel_incomplet_ou_ambigu(rows,count):
    db,_=client(rows=rows,count=count)
    with pytest.raises(IRGNonDisponible):
        simuler_irg_depuis_supabase("50000","2026-10-28","SALARIE",db_client=db)


def test_erreur_reseau_sans_secret():
    db,q=client()
    q.execute.side_effect=RuntimeError("SECRET_DO_NOT_ECHO")
    with pytest.raises(IRGNonDisponible,match="Référentiel IRG inaccessible") as error:
        simuler_irg_depuis_supabase("50000","2026-10-28","SALARIE",db_client=db)
    assert "SECRET_DO_NOT_ECHO" not in str(error.value)
