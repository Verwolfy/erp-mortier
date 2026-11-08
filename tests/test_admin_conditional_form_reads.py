"""Contrôle des chargements Administration sans session ni réseau."""
import ast
from pathlib import Path


def _page():
    source = Path("modules/admin/views.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    return next(node for node in tree.body
                if isinstance(node, ast.FunctionDef)
                and node.name == "show_admin_page")


def test_listes_de_choix_chargees_seulement_si_utilisees():
    page = _page()
    source = ast.unparse(page)
    assert "def _active(*keys):" in source
    assert "st.session_state.get(key) is True" in source
    assert "return can_write and any(" in source
    assert "get_opts('PAYS', PAYS_FALLBACK)" in source
    assert "get_opts('HS_CODE', HS_CODE_FALLBACK)" in source
    # Les options ne doivent plus être chargées sans condition.
    assigns = [n for n in page.body if isinstance(n, ast.Assign)]
    for node in assigns:
        if any(isinstance(x, ast.Name) and x.id.endswith("_opts")
               for target in node.targets for x in ast.walk(target)):
            if "get_opts(" in ast.unparse(node.value):
                assert isinstance(node.value, ast.IfExp)


def test_formulaires_creation_sont_declenches_explicitement():
    source = ast.unparse(_page())
    for name in ("client", "fournisseur", "mp", "product", "sku"):
        assert f"ng_admin_create_{name}" in source
    assert source.count("if can_write and st.checkbox(") == 5


def test_sku_read_only_and_creation_disabled_have_no_catalog_reads():
    page = _page()
    sku_tabs = [
        n for n in ast.walk(page)
        if isinstance(n, ast.If)
        and ast.unparse(n.test) == "active_panel == admin_panels[4]"
    ]
    assert len(sku_tabs) == 1
    sku = sku_tabs[0]
    creation_guards = [
        n for n in sku.body if isinstance(n, ast.If)
        and "ng_admin_create_sku" in ast.unparse(n.test)
    ]
    assert len(creation_guards) == 1
    guarded = ast.unparse(creation_guards[0])
    assert "get_dataframe('Produits', only_active=True)" in guarded
    assert "get_dataframe('MatieresPremieres', only_active=True)" in guarded
    # Autres lectures sur ouverture explicite de l'éditeur
    editors = [
        n for n in sku.body if isinstance(n, ast.If)
        and "ng_admin_full_sku_conditionnement" in ast.unparse(n.test)
    ]
    assert len(editors) == 1
    assert "render_editable_dataframe('SkuConditionnement'" in ast.unparse(editors[0])


def test_les_listes_de_reference_ne_chargent_pas_par_defaut():
    page = _page()
    sections = [
        n for n in ast.walk(page)
        if isinstance(n, ast.If)
        and ast.unparse(n.test) == "active_panel == admin_panels[5]"
    ]
    assert len(sections) == 1
    code = ast.unparse(sections[0])
    assert "ng_admin_open_reference_lists" in code
    assert code.index("ng_admin_open_reference_lists") < code.index("gerer_listes_reference()")
    assert "if can_write:" in code
