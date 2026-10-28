"""Tests lecture réglementaire en lecture seule, sans connexion distante."""
from types import SimpleNamespace
from unittest.mock import Mock
from decimal import Decimal

import pytest

from core.fiscalite_facturation import FiscaliteNonDisponible
from core.fiscalite_service import fiscalite_facture_reglementee


def example():
    return [{
        "code": "TVA_VENTE_TAUX", "valeur": "0.11",
        "unite": "fraction", "date_effet": "2026-01-01", "date_fin": None,
        "statut_juridique": "en_vigueur", "niveau_confiance": "CONFIRMEE",
        "source": "TEST", "date_verification": "2026-01-02",
    }]


def backend(rows=None, count=None):
    rows = example() if rows is None else rows
    query = Mock()
    query.select.return_value = query
    query.in_.return_value = query
    query.order.return_value = query
    query.range.return_value = query
    query.execute.return_value = SimpleNamespace(
        data=rows, count=len(rows) if count is None else count,
    )
    db = Mock()
    db.table.return_value = query
    return db, query


def test_lecture_serveur_et_calcul():
    db, q = backend()
    result = fiscalite_facture_reglementee(
        "100", False, "2026-10-28", db_client=db,
    )
    assert result["montant_tva"] == Decimal("11.00")
    db.table.assert_called_once_with("parametres_reglementaires")
    q.in_.assert_called_once_with("code", ["TVA_VENTE_TAUX"])
    assert q.range.call_args.args == (0, 999)


def test_lecture_tronquee_refusee():
    db, _ = backend(count=1000)
    with pytest.raises(FiscaliteNonDisponible):
        fiscalite_facture_reglementee("10", False, "2026-10-28", db_client=db)


def test_erreur_reseau_masquee():
    db, q = backend()
    q.execute.side_effect = TimeoutError("sensitive internal error")
    with pytest.raises(FiscaliteNonDisponible, match="Registre fiscal indisponible"):
        fiscalite_facture_reglementee("10", False, "2026-10-28", db_client=db)


def test_aucun_taux_par_defaut():
    db, _ = backend(rows=[])
    with pytest.raises(FiscaliteNonDisponible):
        fiscalite_facture_reglementee("10", False, "2026-10-28", db_client=db)


def test_trois_codes_si_especes():
    db, q = backend()
    with pytest.raises(FiscaliteNonDisponible):
        fiscalite_facture_reglementee("10", True, "2026-10-28", db_client=db)
    assert q.in_.call_args.args[1] == [
        "TVA_VENTE_TAUX", "TIMBRE_ESPECES_TAUX", "TIMBRE_ESPECES_PLAFOND",
    ]
