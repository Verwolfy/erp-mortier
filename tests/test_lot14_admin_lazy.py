"""Lot 14 : dix panneaux Administration exclusifs ; aucune lecture hors vue.

La vérification est hors réseau et ne crée ni tiers ni données fiscales.
"""
from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from modules.admin import views as admin
from modules.admin import catalog_search_view
from modules.documents import views as docs


PANELS = (
    "👥 Clients", "🏢 Fournisseurs", "🧪 Matières Premières",
    "🛍️ Produits", "📦 SKU", "📝 Listes de choix",
    "📑 Exonérations TVA (lecture)", "📋 Qualification TVA SKU",
    "📄 Documents NEXTGEN", "📊 Qualité référentiels",
)


@pytest.fixture
def ui(monkeypatch):
    st = MagicMock()
    st.session_state = {
        "user": {"user_id": "USR-TEST", "role": "ADMIN"},
        "authenticated": True,
    }
    st.checkbox.return_value = False
    st.button.return_value = False
    st.form_submit_button.return_value = False
    st.text_input.return_value = ""
    st.columns.side_effect = lambda count: [
        MagicMock() for _ in range(count if isinstance(count, int) else len(count))
    ]
    monkeypatch.setattr(admin, "st", st)
    write = MagicMock(return_value=True)
    monkeypatch.setattr(admin, "has_permission", write)

    get_opts = MagicMock(return_value=["TEST"])
    get_dataframe = MagicMock(return_value=pd.DataFrame())
    edit = MagicMock()
    search = MagicMock()
    quality = MagicMock()
    tax = MagicMock()
    sku_tax = MagicMock()
    nextgen = MagicMock()
    documents = MagicMock()

    monkeypatch.setattr(admin, "get_opts", get_opts)
    monkeypatch.setattr(admin, "get_liste", lambda *_a, **_kw: [])
    monkeypatch.setattr(admin, "liste_to_dict", lambda *_a, **_kw: {})
    monkeypatch.setattr(admin, "get_dataframe", get_dataframe)
    monkeypatch.setattr(admin, "render_editable_dataframe", edit)
    monkeypatch.setattr(catalog_search_view, "render_catalog_search", search)
    monkeypatch.setattr(admin, "_revue_exonerations_tva_clients", tax)
    monkeypatch.setattr(admin, "_revue_qualification_fiscale_sku", sku_tax)
    monkeypatch.setattr(admin, "_revue_nextgen_preparation", nextgen)
    monkeypatch.setattr(docs, "show_documents_page", documents)
    monkeypatch.setattr(
        __import__("modules.admin.finance_rh_quality_view",
                   fromlist=["render_finance_rh_quality"]),
        "render_finance_rh_quality", quality,
    )
    return st, write, get_opts, get_dataframe, edit, search, quality, tax, sku_tax, nextgen, documents


def _choose(ui, index):
    st = ui[0]
    st.selectbox.side_effect = (
        lambda label, options, **kw:
        PANELS[index] if label == "Vue Administration" else list(options)[0]
    )


@pytest.mark.parametrize("index", range(10))
def test_only_selected_admin_panel_runs(ui, index):
    _choose(ui, index)
    admin.show_admin_page()
    st, permission, get_opts, get_dataframe, edit, search, quality, tax, sku_tax, nextgen, documents = ui
    permission.assert_called_once_with("ADMIN", "Administration", "ecriture")
    assert search.call_count == (1 if index in range(5) else 0)
    assert tax.call_count == (1 if index == 6 else 0)
    assert sku_tax.call_count == (1 if index == 7 else 0)
    assert nextgen.call_count == (1 if index == 7 else 0)
    assert documents.call_count == (1 if index == 8 else 0)
    assert quality.call_count == (1 if index == 9 else 0)
    get_opts.assert_not_called()
    get_dataframe.assert_not_called()
    edit.assert_not_called()
    st.tabs.assert_not_called()


def test_flags_from_hidden_forms_cannot_fetch_other_catalogues(ui):
    st, _, get_opts, *_ = ui
    st.session_state.update({
        "ng_admin_create_client": True,
        "ng_admin_full_clients": True,
        "ng_admin_create_mp": True,
        "ng_admin_full_sku_conditionnement": True,
    })
    _choose(ui, 9)  # qualité : aucun catalogue de création nécessaire
    admin.show_admin_page()
    get_opts.assert_not_called()


def test_active_client_form_reads_only_client_catalogues(ui):
    st, _, get_opts, *_ = ui
    st.session_state.update({
        "ng_admin_create_client": True,
        "ng_admin_create_mp": True,  # cet autre panneau est masqué
        "ng_admin_create_sku": True,
    })
    st.checkbox.side_effect = lambda _label, **kw: (
        kw.get("key") == "ng_admin_create_client"
    )
    _choose(ui, 0)
    admin.show_admin_page()
    codes = [c.args[0] for c in get_opts.call_args_list]
    assert codes == ["PAYS", "WILAYA", "CAT_CLIENT"]


def test_read_only_does_not_fetch_form_dropdowns(ui):
    st, permission, get_opts, *_ = ui
    permission.return_value = False
    st.session_state["ng_admin_create_client"] = True
    _choose(ui, 0)
    admin.show_admin_page()
    get_opts.assert_not_called()
    st.info.assert_called()


def test_navigation_offers_ten_choices_and_tracks_activity(ui):
    _choose(ui, 5)
    admin.show_admin_page()
    st = ui[0]
    nav = next(c for c in st.selectbox.call_args_list
               if c.args and c.args[0] == "Vue Administration")
    assert tuple(nav.args[1]) == PANELS
    assert nav.kwargs["on_change"] is admin._mark_admin_activity
    admin._mark_admin_activity()
    assert st.session_state["_erp_admin_interacted"] is True
    assert "last_activity" not in st.session_state


def test_static_ten_panels_and_no_eager_tabs():
    root = Path(__file__).resolve().parents[1]
    code = (root / "modules/admin/views.py").read_text(encoding="utf-8")
    tree = ast.parse(code)
    page = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                and n.name == "show_admin_page")
    assert "st.tabs(" not in ast.unparse(page)
    selected = [ast.unparse(n.test)
                for n in ast.walk(page)
                if isinstance(n, ast.If)
                and ast.unparse(n.test).startswith("active_panel == admin_panels[")]
    indices = [int(item.rsplit("[", 1)[1].split("]", 1)[0]) for item in selected]
    assert Counter(indices) == Counter({**{i: 1 for i in range(9)}, 9: 2})
    assert "key in allowed_keys" in ast.unparse(page)
