"""Prévention des doublons Clients/Fournisseurs, sans accès réseau ni écriture."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from modules.admin.tier_dedup import DuplicateTierError, ensure_new_tier
from modules.admin import service


@pytest.mark.parametrize("kind,pk", [("client", "client_id"),
                                       ("fournisseur", "fournisseur_id")])
@pytest.mark.parametrize("field,new,old", [
    ("nif", " 123 456-789 ", "123456789"),
    ("rc", "16/00-12345", "160012345"),
    ("nom", "  Établissements   SOFIANE  ", "etablissements sofiane"),
])
def test_same_identity_is_blocked(kind, pk, field, new, old):
    existing = [{pk: "EXISTE-1", field: old}]
    data = {"nom": "Nouveau Tiers", field: new}
    if field == "nom":
        data["nom"] = new
    with pytest.raises(DuplicateTierError, match="EXISTE-1"):
        ensure_new_tier(kind=kind, data=data, existing=existing)


def test_empty_legal_identifiers_never_collide():
    ensure_new_tier(kind="client",
                    data={"nom": "Client B", "nif": "", "rc": None},
                    existing=[{"client_id": "CLI-001", "nom": "Client A",
                               "nif": None, "rc": ""}])


def test_same_company_can_be_customer_and_supplier():
    ensure_new_tier(kind="client", data={"nom": "SARL TEST", "nif": "123"},
                    existing=[])
    ensure_new_tier(kind="fournisseur", data={"nom": "SARL TEST", "nif": "123"},
                    existing=[])


@pytest.mark.parametrize("rows", [
    None, [{"nom": "Incomplet"}], ["row"], {"client_id": "CLI-001"},
])
def test_incomplete_reference_is_fail_closed(rows):
    with pytest.raises(RuntimeError):
        ensure_new_tier(kind="client", data={"nom": "Nouveau"}, existing=rows)


def test_preflight_blocks_insert_on_any_duplicate(monkeypatch):
    reader = MagicMock(return_value=[
        {"client_id": "CLI-001", "nom": "SARL BETA", "nif": "123-456",
         "rc": "16/00/5678"}
    ])
    writer = MagicMock()
    monkeypatch.setattr(service, "fetch_data_paginated", reader)
    monkeypatch.setattr(service, "insert_hybrid", writer)
    with pytest.raises(DuplicateTierError):
        service.add_client({"nom": "Sarl beta", "nif": "", "rc": ""})
    with pytest.raises(DuplicateTierError):
        service.add_client({"nom": "Société différente", "nif": "123456"})
    with pytest.raises(DuplicateTierError):
        service.add_client({"nom": "Société différente", "rc": "16005678"})
    writer.assert_not_called()
    assert reader.call_count == 3
    assert all(call.kwargs["page_size"] == 500 for call in reader.call_args_list)


def test_provider_preflight_runs_before_creating_identifier(monkeypatch):
    reader = MagicMock(return_value=[
        {"fournisseur_id": "FRN-0001", "nom": "FOURNISSEUR BETA", "nif": "123"}
    ])
    writer = MagicMock()
    identity = MagicMock()
    monkeypatch.setattr(service, "fetch_data_paginated", reader)
    monkeypatch.setattr(service, "insert_hybrid", writer)
    monkeypatch.setattr(service, "generate_unique_id", identity)
    with pytest.raises(DuplicateTierError):
        service.add_fournisseur({"nom": "Fournisseur Beta"})
    identity.assert_not_called()
    writer.assert_not_called()


@pytest.mark.parametrize("exception", [PermissionError("Accès refusé"),
                                       RuntimeError("Lecture indisponible"),
                                       ValueError("Lecture tronquée")])
def test_read_failure_blocks_write(monkeypatch, exception):
    monkeypatch.setattr(service, "fetch_data_paginated",
                        MagicMock(side_effect=exception))
    writer = MagicMock()
    monkeypatch.setattr(service, "insert_hybrid", writer)
    with pytest.raises(type(exception)):
        service.add_client({"nom": "Client nouveau"})
    writer.assert_not_called()


def test_valid_creation_preserves_input_and_generates_unique_id(monkeypatch):
    monkeypatch.setattr(service, "fetch_data_paginated",
                        MagicMock(return_value=[
                            {"client_id": "CLI-0001", "nom": "Client A"}
                        ]))
    monkeypatch.setattr(service, "generate_unique_id",
                        lambda prefix, ids: "CLI-0002")
    writer = MagicMock(return_value=[{"client_id": "CLI-0002"}])
    monkeypatch.setattr(service, "insert_hybrid", writer)
    new = {"nom": "Client B", "nif": "99999"}
    assert service.add_client(new) == "CLI-0002"
    assert new == {"nom": "Client B", "nif": "99999"}
    writer.assert_called_once()
    assert writer.call_args.args[0] == "clients"
    assert writer.call_args.args[1]["client_id"] == "CLI-0002"


def test_comparison_never_puts_legal_identifier_in_error():
    with pytest.raises(DuplicateTierError) as err:
        ensure_new_tier(kind="client", data={"nom": "BETA", "nif": "NIFPRIVATE123"},
                        existing=[{"client_id": "CLI-002", "nom": "OTHER",
                                   "nif": "NIF PRIVATE 123"}])
    assert "NIFPRIVATE123" not in str(err.value)
    assert "CLI-002" in str(err.value)
