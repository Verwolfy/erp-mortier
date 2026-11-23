"""Les six familles de pièces enregistrées reçoivent les trois actions documentaires."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def ui(monkeypatch):
    st = MagicMock()
    st.session_state = {}
    monkeypatch.setitem(sys.modules, "streamlit", st)
    source = Path(__file__).resolve().parents[1] / "modules/documents/row_actions.py"
    spec = importlib.util.spec_from_file_location("document_row_actions_test", source)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, st


@pytest.mark.parametrize("kind,col", [
    ("Ordre de fabrication", "of_id"),
    ("Bon de livraison", "bl_id"),
    ("Facture (aperçu interne)", "facture_id"),
    ("Bon de réception", "bon_reception_id"),
    ("Commande client", "commande_vente_id"),
    ("Commande fournisseur", "commande_achat_id"),
])
def test_all_supported_kinds_get_buttons(ui, kind, col):
    mod, st = ui
    mod.show_recorded_documents(
        [{col: "D-1", "statut": "EN_ATTENTE"}, {col: "D-2", "statut": "VALIDE"}],
        kind=kind, id_column=col, user_id="USR-1", scope="test",
    )
    table = st.dataframe.call_args.kwargs
    assert table["column_order"][:4] == [col, "Consulter", "Imprimer", "PDF"]
    assert set(table["column_config"]) == {"Consulter", "Imprimer", "PDF"}
    assert st.column_config.ButtonColumn.call_count == 3
    st.download_button.assert_not_called()


@pytest.mark.parametrize("bad_row", [-1, 9, True, "1", None])
def test_out_of_range_or_invalid_selection_is_ignored(ui, bad_row):
    mod, st = ui
    st.session_state["click"] = {"row": bad_row}
    mod._clicked("achats", "USR-1", "pdf", ("D-1", "D-2"), "click")
    assert mod._key("achats", "USR-1", "selected") not in st.session_state


def test_click_selects_only_target_reference(ui):
    mod, st = ui
    st.session_state["click"] = {"row": 1}
    mod._clicked("achats", "USR-1", "pdf", ("D-1", "D-2"), "click")
    assert st.session_state[mod._key("achats", "USR-1", "selected")] == ("pdf", "D-2")


def test_duplicate_identifiers_block_actions(ui):
    mod, st = ui
    mod.show_recorded_documents(
        [{"of_id": "DUP"}, {"of_id": "DUP"}],
        kind="Ordre de fabrication", id_column="of_id",
        user_id="USR-1", scope="test")
    st.error.assert_called_once()
    st.column_config.ButtonColumn.assert_not_called()


def test_no_made_up_document_kinds(ui):
    mod, st = ui
    with pytest.raises(ValueError):
        mod.show_recorded_documents(
            [{"id": "BUL-1"}], kind="Bulletin de paie",
            id_column="id", user_id="USR-1", scope="rh")


def test_invalid_click_cannot_cross_user(ui):
    mod, st = ui
    st.session_state["click"] = {"row": 0}
    mod._clicked("achats", "USR-1", "consulter", ("D-1",), "click")
    assert mod._key("achats", "USR-2", "selected") not in st.session_state


def test_ui_wiring_keeps_historical_business_actions():
    root = Path(__file__).resolve().parents[1]
    achats = (root / "modules/achats/views.py").read_text()
    ventes = (root / "modules/ventes/views.py").read_text()
    prod = (root / "modules/production/views.py").read_text()
    drafts = (root / "modules/documents/views.py").read_text()
    assert 'id_column="bon_reception_id"' in achats
    assert 'id_column="commande_vente_id"' in ventes
    assert 'id_column="bl_id"' in ventes
    assert 'id_column="facture_id"' in ventes
    assert 'id_column="of_id"' in prod
    assert 'ng_doc_draft_print' in drafts
    assert 'ng_doc_draft_pdf' in drafts
