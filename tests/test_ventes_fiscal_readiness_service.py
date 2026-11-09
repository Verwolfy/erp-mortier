"""Lecture SQL TVA SKU via service Ventes, sans réseau ni mutation."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from modules.ventes import service


def test_lecture_tva_sql_passe_par_service_et_date_validee(monkeypatch):
    client = Mock()
    client.rpc.return_value.execute.return_value = SimpleNamespace(data=[
        {"sku_id": "SKU-TEST", "etat_technique": "SANS_FICHE",
         "fiches_applicables": 0, "code_tva": None}
    ])
    monkeypatch.setattr(service, "_stock_rpc_client", lambda: client)

    result = service.lire_diagnostic_fiscal_sku("2026-11-09")

    assert result[0]["sku_id"] == "SKU-TEST"
    client.rpc.assert_called_once_with("erp_tva_sku_readiness", {
        "p_date": "2026-11-09"
    })
    client.table.assert_not_called()


@pytest.mark.parametrize("date", [None, "2026-02-30", "2026-1-9", "20261109", 42])
def test_date_invalide_refusee_avant_appel_sql(monkeypatch, date):
    client = Mock()
    monkeypatch.setattr(service, "_stock_rpc_client", lambda: client)
    with pytest.raises(ValueError):
        service.lire_diagnostic_fiscal_sku(date)
    client.rpc.assert_not_called()


@pytest.mark.parametrize("data", [None, {}, "vide", [None], [{"sku_id":"A"}] * 10001])
def test_diagnostic_sql_incomplet_refuse(monkeypatch, data):
    client = Mock()
    client.rpc.return_value.execute.return_value = SimpleNamespace(data=data)
    monkeypatch.setattr(service, "_stock_rpc_client", lambda: client)
    with pytest.raises(RuntimeError, match="incomplet"):
        service.lire_diagnostic_fiscal_sku("2026-11-09")


def test_diagnostic_sql_erreur_ne_lance_pas_autre_operation(monkeypatch):
    client = Mock()
    client.rpc.side_effect = TimeoutError("RESEAU")
    monkeypatch.setattr(service, "_stock_rpc_client", lambda: client)
    with pytest.raises(RuntimeError, match="indisponible"):
        service.lire_diagnostic_fiscal_sku("2026-11-09")
    client.rpc.assert_called_once()
    client.table.assert_not_called()
