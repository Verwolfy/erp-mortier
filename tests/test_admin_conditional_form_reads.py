"""Contrôle des chargements Administration sans session ni réseau."""
import ast
from pathlib import Path


def _page():
    source = Path("modules/admin/views.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    return next(node for node in tree.body
                if isinstance(node, ast.FunctionDef)
                and node.name == "show_admin_page")


def test_listes_de_choix_ignorees_en_lecture_seule():
    page = _page()
    guards = [
        n for n in page.body if isinstance(n, ast.If)
        and ast.unparse(n.test) == "can_write"
        and any(isinstance(child, ast.Assign)
                and any("get_opts(" in ast.unparse(x) for x in child.value.elts)
                if isinstance(child.value, ast.Tuple) else
                "get_opts(" in ast.unparse(child)
                for child in n.body if isinstance(child, ast.Assign))
    ]
    assert len(guards) == 1
    code = ast.unparse(guards[0])
    assert 'get_opts("PAYS", PAYS_FALLBACK)' in code
    assert 'get_opts("HS_CODE", HS_CODE_FALLBACK)' in code
    assert "pays_opts, wilaya_opts, unite_opts = ([], [], [])" in code


def test_sku_read_only_and_creation_disabled_have_no_catalog_reads():
    page = _page()
    sku_tabs = [
        n for n in ast.walk(page)
        if isinstance(n, ast.With)
        and any(ast.unparse(item.context_expr) == "tab5" for item in n.items)
    ]
    assert len(sku_tabs) == 1
    sku = sku_tabs[0]
    creation_guards = [
        n for n in sku.body if isinstance(n, ast.If)
        and "ng_admin_create_sku" in ast.unparse(n.test)
    ]
    assert len(creation_guards) == 1
    guarded = ast.unparse(creation_guards[0])
    assert 'get_dataframe("Produits", only_active=True)' in guarded
    assert 'get_dataframe("MatieresPremieres", only_active=True)' in guarded
    # Autres lectures sur ouverture explicite de l'éditeur
    editors = [
        n for n in sku.body if isinstance(n, ast.If)
        and "ng_admin_full_sku_conditionnement" in ast.unparse(n.test)
    ]
    assert len(editors) == 1
    assert 'render_editable_dataframe("SkuConditionnement"' in ast.unparse(editors[0])
