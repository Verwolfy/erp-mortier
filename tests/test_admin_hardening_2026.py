"""Tests unitaires du durcissement Administration (aucun appel réseau)."""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest


@pytest.fixture
def service(monkeypatch):
    st = types.ModuleType("streamlit")
    st.cache_data = lambda **kwargs: lambda fn: fn
    monkeypatch.setitem(sys.modules, "streamlit", st)

    db = types.ModuleType("core.db_service")
    db.fetch_data = MagicMock(return_value=[])
    db.insert_hybrid = MagicMock(return_value=[{"id": "ok"}])
    db.update_hybrid = MagicMock(return_value=[{"client_id": "CLI-001"}])
    db.get_supabase_client = MagicMock()
    monkeypatch.setitem(sys.modules, "core.db_service", db)

    utils = types.ModuleType("core.utils")
    utils.generate_unique_id = MagicMock(side_effect=lambda prefix, _: f"{prefix}-001")
    monkeypatch.setitem(sys.modules, "core.utils", utils)

    auth_service = types.ModuleType("modules.auth.service")
    auth_service.hash_password = lambda raw: "bcrypt-hash-for-test"
    monkeypatch.setitem(sys.modules, "modules.auth.service", auth_service)

    path = Path(__file__).resolve().parents[1] / "modules" / "admin" / "service.py"
    name = "_admin_service_hardened_unit"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _df():
    return pd.DataFrame([{"client_id": "CLI-001", "nom": "Client A"},
                         {"client_id": "CLI-002", "nom": "Client B"}])


@pytest.mark.parametrize("sheet,pk,sensitive", [
    ("MatieresPremieres", "mp_id", "cmp_actuel"),
    ("MatieresPremieres", "mp_id", "unite_stock"),
    ("MatieresPremieres", "mp_id", "poids_net"),
    ("Produits", "pf_id", "unite_production"),
    ("Produits", "pf_id", "recette_id"),
    ("SkuConditionnement", "sku_id", "facteur_conversion"),
    ("SkuConditionnement", "sku_id", "poids_net"),
    ("SkuConditionnement", "sku_id", "emballage_mp_id"),
    ("SkuConditionnement", "sku_id", "pf_id"),
])
def test_technical_fields_blocked(service, sheet, pk, sensitive):
    frame = pd.DataFrame([{pk: "ID-1", sensitive: "old"}])
    with pytest.raises(ValueError, match="protégée"):
        service.sauvegarder_modifications(sheet, pk, frame, {"0": {sensitive: "bad"}})
    service.update_hybrid.assert_not_called()


def test_multirow_fails_without_writes(service):
    with pytest.raises(ValueError, match="une seule ligne"):
        service.sauvegarder_modifications("Clients", "client_id", _df(), {
            "0": {"nom": "A"}, "1": {"nom": "B"}
        })
    service.update_hybrid.assert_not_called()


def test_primary_key_and_spoofed_columns_blocked(service):
    with pytest.raises(ValueError):
        service.sauvegarder_modifications("Clients", "nom", _df(), {"0": {"nom": "B"}})
    with pytest.raises(ValueError):
        service.sauvegarder_modifications("Clients", "client_id", _df(), {"0": {"client_id": "Other"}})
    service.update_hybrid.assert_not_called()


def test_single_allowed_update_requires_matching_confirmation(service):
    assert service.sauvegarder_modifications("Clients", "client_id", _df(), {
        "0": {"nom": "Client B"}
    }) is True
    service.update_hybrid.assert_called_once_with("clients", "client_id", "CLI-001", {"nom": "Client B"})


@pytest.mark.parametrize("response", [None, [], ["unexpected"], [{"client_id": "CLI-002"}]])
def test_update_not_confirmed_never_succeeds(service, response):
    service.update_hybrid.return_value = response
    with pytest.raises(RuntimeError):
        service.sauvegarder_modifications("Clients", "client_id", _df(), {"0": {"nom": "Autre"}})


@pytest.mark.parametrize("method,args", [
    ("add_client", ({"nom": "Client"},)),
    ("add_fournisseur", ({"nom": "Fournisseur"},)),
    ("add_produit", ({"nom": "Produit"},)),
    ("add_matiere_premiere", ({"nom": "Matière"},)),
    ("add_sku", ({"format": "SAC 25KG"},)),
])
def test_creation_requires_supabase_confirmation(service, method, args):
    service.insert_hybrid.return_value = None
    with pytest.raises(RuntimeError):
        getattr(service, method)(*args)


def test_user_directory_never_selects_hash(service):
    supa = service.get_supabase_client.return_value
    supa.table.return_value.select.return_value.execute.return_value.data = [{
        "user_id": "USR-001", "nom": "Test", "role": "ADMIN", "actif": "OUI"
    }]
    users = service.get_users()
    assert "hash_mdp" not in users.columns
    supa.table.return_value.select.assert_called_once_with("user_id,nom,login,role,actif")


def test_new_user_uses_central_password_policy(service):
    service.get_supabase_client.return_value.table.return_value.select.return_value.execute.return_value.data = []
    assert service.add_user("Test", "test", "mot-de-passe-test", "ADMIN") == "USR-001"
    data = service.insert_hybrid.call_args.args[1]
    assert data["hash_mdp"] == "bcrypt-hash-for-test"
    assert data["hash_mdp"] != "mot-de-passe-test"


def test_permission_creation_fails_if_insert_unconfirmed(service):
    service.insert_hybrid.return_value = []
    with pytest.raises(RuntimeError):
        service.add_permission("TEST", "RH", "OUI", "NON")


def test_editable_fields_excludes_technical_columns(service):
    assert "cmp_actuel" not in service.EDITABLE_FIELDS["MatieresPremieres"]
    assert "facteur_conversion" not in service.EDITABLE_FIELDS["SkuConditionnement"]
    assert "prix_vente_defaut" in service.EDITABLE_FIELDS["SkuConditionnement"]
    assert "nom" in service.EDITABLE_FIELDS["Clients"]


def test_active_status_rejects_invalid_values(service):
    with pytest.raises(ValueError, match="OUI ou NON"):
        service.sauvegarder_modifications("Clients", "client_id", _df(), {"0": {"actif": "INVALID"}})
    service.update_hybrid.assert_not_called()
