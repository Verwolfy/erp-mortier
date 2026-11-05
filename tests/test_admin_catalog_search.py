"""Recherche des référentiels : bornes, droits et colonnes minimales."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from modules.admin import catalog_search as search


class Query:
    def __init__(self, rows, count):
        self.rows, self.count = rows, count
        self.filters = []
        self.projection = None
        self.sort = None
        self.bounds = None

    def select(self, fields, *, count):
        assert count == "exact"
        self.projection = fields
        return self

    def ilike(self, field, value):
        self.filters.append((field, value))
        return self

    def order(self, field):
        self.sort = field
        return self

    def range(self, start, end):
        self.bounds = (start, end)
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows, count=self.count)


def test_search_is_server_side_and_restricts_columns(monkeypatch):
    rows = [{"client_id": "C-01", "nom": "Alpha", "categorie_client": "B2B",
             "actif": "OUI"}]
    q, guard = Query(rows, 1), Mock()
    monkeypatch.setattr(search.db, "_require_read_permission", guard)
    monkeypatch.setattr(search.db, "get_supabase_client",
                        lambda: SimpleNamespace(table=lambda table: q))
    got, total = search.search_referentiel("clients", "Alpha")
    assert got == rows and total == 1
    guard.assert_called_once_with("clients")
    assert q.projection == "client_id,nom,categorie_client,actif"
    assert "email_contact" not in q.projection
    assert q.filters == [("nom", "%Alpha%")]
    assert q.sort == "client_id"
    assert q.bounds == (0, 49)


@pytest.mark.parametrize("params", [
    ("users", "Alpha", "nom", 1),
    ("clients", "a", "nom", 1),
    ("clients", "a%", "nom", 1),
    ("clients", "_x", "nom", 1),
    ("clients", "ABC", "email_contact", 1),
    ("clients", "ABC", "nom", 0),
    ("clients", "ABC", "nom", True),
])
def test_invalid_request_fails_before_network(monkeypatch, params):
    monkeypatch.setattr(search.db, "get_supabase_client",
                        Mock(side_effect=AssertionError("No DB access")))
    with pytest.raises(ValueError):
        search.search_referentiel(params[0], params[1], field=params[2], page=params[3])


def test_permission_denial_blocks_query(monkeypatch):
    monkeypatch.setattr(search.db, "_require_read_permission",
                        Mock(side_effect=PermissionError("Forbidden")))
    client = Mock(side_effect=AssertionError("No DB access"))
    monkeypatch.setattr(search.db, "get_supabase_client", client)
    with pytest.raises(PermissionError):
        search.search_referentiel("fournisseurs", "Nom")
    client.assert_not_called()


@pytest.mark.parametrize("rows,count", [
    (None, 0), ([], None), ([], 1),
    ([{"pf_id": "P1"}, {"pf_id": "P1"}], 2),
    ([{"pf_id": ""}], 1), ([{"pf_id": "P1"}], 100001),
])
def test_search_never_returns_partial_or_bad_result(monkeypatch, rows, count):
    q = Query(rows, count)
    monkeypatch.setattr(search.db, "_require_read_permission", Mock())
    monkeypatch.setattr(search.db, "get_supabase_client",
                        lambda: SimpleNamespace(table=lambda table: q))
    with pytest.raises(RuntimeError):
        search.search_referentiel("produits", "Pierre")


def test_editors_are_opt_in_and_search_does_not_write():
    from pathlib import Path
    source = Path("modules/admin/views.py").read_text(encoding="utf-8")
    for table in ("clients", "fournisseurs", "produits", "matieres_premieres", "sku_conditionnement"):
        assert f'render_catalog_search("{table}")' in source
        assert f'key="ng_admin_full_{table}"' in source
    code = Path("modules/admin/catalog_search.py").read_text(encoding="utf-8")
    assert "insert_hybrid" not in code
    assert "update_hybrid" not in code


def test_matieres_premieres_par_nom(monkeypatch):
    rows = [{"mp_id": "MP-12", "nom": "Ciment gris",
             "categorie_mp": "LIANT", "actif": "OUI"}]
    q = Query(rows, 1)
    check = Mock()
    monkeypatch.setattr(search.db, "_require_read_permission", check)
    monkeypatch.setattr(search.db, "get_supabase_client",
                        lambda: SimpleNamespace(table=lambda _: q))
    result, total = search.search_referentiel("matieres_premieres", "Ciment")
    assert result == rows and total == 1
    assert q.projection == "mp_id,nom,categorie_mp,actif"
    assert q.filters == [("nom", "%Ciment%")]
    check.assert_called_once_with("matieres_premieres")


def test_sku_par_format_et_reference(monkeypatch):
    rows = [{"sku_id": "SKU-1", "format": "Sac 25 kg",
             "pf_id": "PF-1", "actif": "OUI"}]
    q = Query(rows, 1)
    monkeypatch.setattr(search.db, "_require_read_permission", Mock())
    monkeypatch.setattr(search.db, "get_supabase_client",
                        lambda: SimpleNamespace(table=lambda _: q))
    found, count = search.search_referentiel("sku_conditionnement", "Sac 25")
    assert found == rows and count == 1
    assert q.projection == "sku_id,format,pf_id,actif"
    assert q.filters == [("format", "%Sac 25%")]
    q.filters.clear()
    search.search_referentiel("sku_conditionnement", "SKU-1", field="sku_id")
    assert q.filters == [("sku_id", "%SKU-1%")]


def test_sku_ne_permet_pas_champ_inexistant(monkeypatch):
    client = Mock(side_effect=AssertionError("Aucun appel réseau attendu"))
    monkeypatch.setattr(search.db, "get_supabase_client", client)
    with pytest.raises(ValueError):
        search.search_referentiel("sku_conditionnement", "Sac 25", field="nom")
    client.assert_not_called()


def test_catalog_view_uses_format_for_sku():
    from pathlib import Path
    source = Path("modules/admin/catalog_search_view.py").read_text(encoding="utf-8")
    assert "identifier, display_field, _ = CATALOGS[table]" in source
    assert "[display_field, identifier]" in source
    admin = Path("modules/admin/views.py").read_text(encoding="utf-8")
    assert admin.index('key="ng_admin_full_sku_conditionnement"') < admin.index(
        'df_produits = get_dataframe("Produits")', admin.index('render_catalog_search("sku_conditionnement")'))
