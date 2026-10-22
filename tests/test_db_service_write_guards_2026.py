"""Tests du correctif de garde d'ecriture - sans connexion reseau."""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def ctx(monkeypatch):
    class FakeQuery:
        def __init__(self, table, database):
            self.table = table
            self.database = database
            self.mode = None
            self.data = None
            self.filter_id = None

        def insert(self, data):
            self.mode = "insert"
            self.data = data
            return self

        def update(self, data):
            self.mode = "update"
            self.data = data
            return self

        def eq(self, column, value):
            self.filter_id = (column, value)
            return self

        def execute(self):
            self.database.calls.append((self.table, self.mode, self.data, self.filter_id))
            if self.database.error is not None:
                raise self.database.error
            if self.database.custom_response is not None:
                return SimpleNamespace(data=self.database.custom_response)
            if self.mode == "insert":
                return SimpleNamespace(data=[dict(self.data)])
            return SimpleNamespace(data=[{**self.data, self.filter_id[0]: self.filter_id[1]}])

    class FakeDatabase:
        def __init__(self):
            self.calls = []
            self.error = None
            self.custom_response = None

        def table(self, name):
            return FakeQuery(name, self)

    fake_db = FakeDatabase()
    st = types.ModuleType("streamlit")
    st.cache_resource = lambda fn: fn
    st.cache_data = lambda **kw: lambda fn: fn
    st.session_state = {}
    monkeypatch.setitem(sys.modules, "streamlit", st)

    supabase = types.ModuleType("supabase")
    supabase.Client = type("Client", (), {})
    supabase.create_client = lambda *args: fake_db
    monkeypatch.setitem(sys.modules, "supabase", supabase)

    core = types.ModuleType("core")
    core.__path__ = []
    monkeypatch.setitem(sys.modules, "core", core)
    sheets = types.ModuleType("core.sheets_service")
    sheets.append_rows_batch = lambda *a, **kw: None
    sheets.update_multiple_cells_by_id = lambda *a, **kw: None
    monkeypatch.setitem(sys.modules, "core.sheets_service", sheets)
    logger = types.ModuleType("core.logger")
    logger.log_error = lambda *a, **kw: None
    monkeypatch.setitem(sys.modules, "core.logger", logger)
    utils = types.ModuleType("core.utils")
    utils.get_local_now = lambda: None
    monkeypatch.setitem(sys.modules, "core.utils", utils)
    config = types.ModuleType("config")
    config.__path__ = []
    monkeypatch.setitem(sys.modules, "config", config)
    roles = types.ModuleType("config.roles")
    roles.has_permission = lambda *a: True
    monkeypatch.setitem(sys.modules, "config.roles", roles)

    file_path = Path(__file__).resolve().parents[1] / "core" / "db_service.py"
    if not file_path.is_file():
        file_path = Path(__file__).resolve().parents[1] / "core" / "db_service.py"
    spec = importlib.util.spec_from_file_location("_tested_db_service_guard", file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.get_supabase_client = lambda: fake_db
    module.check_server_permission = lambda table: True
    module.log_action = lambda *args: None
    module._sync_google_sheets_insert = lambda *args: None
    module._sync_google_sheets_update = lambda *args: None
    return SimpleNamespace(db=fake_db, module=module)


@pytest.mark.parametrize("table", [
    "fournisseurs", "matieres_premieres", "produits", "sku_conditionnement",
    "clients", "users", "permissions", "listes_reference",
    "pipeline", "interactions", "recettes", "lignes_recette",
    "ordres_fabrication", "employes", "demandes_conges",
])
def test_insert_authorized_tables(ctx, table):
    col = ctx.module.SCHEMA_CONFIG[table]["cols"][0]
    value = "TMP-TEST"
    assert ctx.module.insert_hybrid(table, {col: value}) == [{col: value}]
    assert ctx.db.calls[-1][0] == table


@pytest.mark.parametrize("table", [
    "mouvements", "mouvements_pf", "lots", "stock_actuel",
    "stock_actuel_pf", "consommations_of", "controle_qualite",
    "factures", "lignes_facture", "reglements", "lettrage",
    "ecritures_comptables", "commandes_achats", "compteurs",
])
def test_insert_transactional_tables_denied(ctx, table):
    with pytest.raises(PermissionError, match="RPC"):
        ctx.module.insert_hybrid(table, {"foo": "bar"})
    assert not ctx.db.calls


@pytest.mark.parametrize("table,pk,col", [
    ("fournisseurs", "fournisseur_id", "nom"),
    ("matieres_premieres", "mp_id", "stock_mini"),
    ("produits", "pf_id", "nom"),
    ("sku_conditionnement", "sku_id", "prix_vente_defaut"),
    ("clients", "client_id", "adresse"),
    ("listes_reference", "id", "actif"),
])
def test_update_allowed_columns_primary_key(ctx, table, pk, col):
    result = ctx.module.update_hybrid(table, pk, "T-1", {col: "OUI"})
    assert result == [{col: "OUI", pk: "T-1"}]
    assert ctx.db.calls == [(table, "update", {col: "OUI"}, (pk, "T-1"))]


@pytest.mark.parametrize("table,pk,col", [
    ("matieres_premieres", "mp_id", "cmp_actuel"),
    ("matieres_premieres", "mp_id", "unite_stock"),
    ("sku_conditionnement", "sku_id", "facteur_conversion"),
    ("sku_conditionnement", "sku_id", "poids_net"),
    ("produits", "pf_id", "unite_production"),
    ("produits", "pf_id", "recette_id"),
    ("clients", "client_id", "client_id"),
])
def test_update_protected_columns_denied(ctx, table, pk, col):
    with pytest.raises(PermissionError, match="protegee"):
        ctx.module.update_hybrid(table, pk, "1", {col: "BAD"})
    assert not ctx.db.calls


def test_update_rejects_wrong_id(ctx):
    with pytest.raises(ValueError, match="primaire"):
        ctx.module.update_hybrid("clients", "pays", "DZ", {"nom": "TEST"})
    assert not ctx.db.calls


def test_update_rejects_transactional_tables(ctx):
    with pytest.raises(PermissionError, match="RPC"):
        ctx.module.update_hybrid("stock_actuel", "mp_id", "1", {"quantite_disponible": 100})
    assert not ctx.db.calls


def test_permission_checked_before_write(ctx):
    ctx.module.check_server_permission = lambda name: False
    with pytest.raises(PermissionError):
        ctx.module.insert_hybrid("clients", {"client_id": "TEST"})
    assert not ctx.db.calls


def test_db_error_not_silently_turned_to_none(ctx):
    ctx.db.error = RuntimeError("private server error")
    with pytest.raises(RuntimeError, match="non confirme") as captured:
        ctx.module.insert_hybrid("clients", {"client_id": "TEST"})
    assert "private server error" not in str(captured.value)


def test_insert_empty_response_not_success(ctx):
    ctx.db.custom_response = []
    with pytest.raises(RuntimeError, match="non verifiable"):
        ctx.module.insert_hybrid("clients", {"client_id": "TEST"})


def test_update_empty_response_not_success(ctx):
    ctx.db.custom_response = []
    with pytest.raises(RuntimeError, match="non verifiable"):
        ctx.module.update_hybrid("clients", "client_id", "TEST", {"nom": "A"})


def test_reference_pk_zero_changes_are_denied(ctx):
    with pytest.raises(ValueError):
        ctx.module.update_hybrid("listes_reference", "id", "", {"actif": "NON"})
    assert not ctx.db.calls
