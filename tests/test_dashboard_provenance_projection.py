"""OPT-03 : preuve offline de la projection de provenance et de son isolation."""
from __future__ import annotations

import pytest

from core.strict_reads import DataReadError
from modules.dashboards import service


def _fake_identifiers(monkeypatch, data):
    calls = []

    def fetch(table, *, only_primary_key=False):
        assert only_primary_key is True
        calls.append(table)
        return [dict(row) for row in data.get(table, [])]

    monkeypatch.setattr(service, "fetch_provenance_identifiers", fetch)
    return calls


def test_render_reads_only_ids_once_for_all_six_sources(monkeypatch):
    rows = {
        "factures": [{"facture_id": "DEMO26-F1"}, {"facture_id": "FAC-1"}],
        "reglements": [{"reglement_id": "SIM26-R1"}],
        "ordres_fabrication": [{"of_id": "OF-1"}],
        "commandes_achats": [{"commande_achat_id": "DEMO26-A1"}],
        "pipeline": [{"opportunite_id": "OP-1"}],
        "employes": [{"employe_id": "SIM26-RH1"}],
    }
    calls = _fake_identifiers(monkeypatch, rows)
    monkeypatch.setattr(
        service, "fetch_data",
        lambda *_args: pytest.fail("Téléchargement de lignes complètes interdit"),
    )
    with service.dashboard_read_scope():
        first = service.get_dashboard_data_provenance()
        again = service.get_dashboard_data_provenance()
    assert first == again
    assert first["marked"] == 4
    assert len(first["sources"]) == 6
    assert first["sources"][0] == {
        "Source": "Factures", "Références DEMO/SIM": 1, "Total": 2
    }
    assert calls == [table for table, _, _ in service._PROVENANCE_SOURCES]


def test_provenance_cache_does_not_cross_render_scope(monkeypatch):
    calls = _fake_identifiers(monkeypatch, {})
    with service.dashboard_read_scope():
        service.get_dashboard_data_provenance()
    with service.dashboard_read_scope():
        service.get_dashboard_data_provenance()
    assert len(calls) == 12


def test_existing_full_kpi_read_is_reused_instead_of_id_read(monkeypatch):
    calls = _fake_identifiers(monkeypatch, {})
    actual = []

    def read(table):
        actual.append(table)
        return [{"facture_id": "SIM-DOC-1"}] if table == "factures" else []

    monkeypatch.setattr(service, "fetch_data", read)
    with service.dashboard_read_scope():
        service.charger_donnees("factures")
        result = service.get_dashboard_data_provenance()
    assert actual == ["factures"]
    assert calls == [table for table, _, _ in service._PROVENANCE_SOURCES
                     if table != "factures"]
    assert result["marked"] == 1


def test_invalid_provenance_id_fails_closed_and_never_cached(monkeypatch):
    calls = _fake_identifiers(monkeypatch, {
        "factures": [{"facture_id": None}],
    })
    with service.dashboard_read_scope():
        for _ in range(2):
            with pytest.raises(DataReadError, match="provenance"):
                service.get_dashboard_data_provenance()
    # L'accès a échoué sur le contrôle métier, sans faux total zéro.
    assert calls == ["factures"]


def test_failed_provenance_fetch_does_not_get_cached(monkeypatch):
    calls = []

    def deny(table, *, only_primary_key=False):
        calls.append(table)
        raise PermissionError("Permission refusée")

    monkeypatch.setattr(service, "fetch_provenance_identifiers", deny)
    with service.dashboard_read_scope():
        for _ in range(2):
            with pytest.raises(PermissionError):
                service.get_dashboard_data_provenance()
    assert calls == ["factures", "factures"]


def test_demo_provenance_never_reads_remote_identifiers(monkeypatch):
    monkeypatch.setattr(
        service, "fetch_provenance_identifiers",
        lambda *_args, **_kwargs: pytest.fail("DEM0 ne doit pas accéder au réseau"),
    )
    data = {table: [] for table, _, _ in service._PROVENANCE_SOURCES}
    data["pipeline"] = [{"opportunite_id": "DEMO-TEST-1"}]
    with service.dashboard_read_scope(demo_rows=data):
        result = service.get_dashboard_data_provenance()
    assert result["marked"] == 1
    assert len(result["sources"]) == 6


def test_unscoped_legacy_call_remains_backward_compatible(monkeypatch):
    calls = []

    def load(table):
        calls.append(table)
        return [{"facture_id": "DEMO-ONE"}] if table == "factures" else []

    monkeypatch.setattr(service, "fetch_data", load)
    monkeypatch.setattr(
        service, "fetch_provenance_identifiers",
        lambda *_args, **_kwargs: pytest.fail("Unscoped uses legacy full reads"),
    )
    result = service.get_dashboard_data_provenance()
    assert result["marked"] == 1
    assert len(calls) == 6
