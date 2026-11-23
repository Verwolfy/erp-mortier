"""Achats : unité et conditionnement visibles avant la création du BC.

Toutes les données et les interactions Streamlit sont simulées en mémoire.
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pandas as pd

from tests.test_achats_views_security import ui


def _configure_new_order(ui, *, unit="PCS", packaging="Carton", add=False):
    ui.mod.get_fournisseurs_actifs = MagicMock(return_value=pd.DataFrame([
        {"fournisseur_id": "FOU-1", "nom": "Fournisseur test", "actif": "OUI"}
    ]))
    ui.mod.get_mp_actives = MagicMock(return_value=pd.DataFrame([
        {"mp_id": "NG-EMB-BIDON-5L", "nom": "Bidon 5 litres",
         "unite_stock": unit, "type_emballage": packaging, "actif": "OUI"},
    ]))
    choices = {
        "Vue Achats": "➕ Nouvelle Commande",
        "Fournisseur": "FOU-1",
        "Article": "NG-EMB-BIDON-5L",
        "Devise": "DZD",
        "Type d'achat": "Emballage",
    }
    ui.st.selectbox.side_effect = (
        lambda label, options, **kwargs: choices.get(label, list(options)[0])
    )
    ui.st.button.return_value = False
    col_sets = []

    def columns(spec):
        out = []
        n = spec if isinstance(spec, int) else len(spec)
        for _ in range(n):
            col = MagicMock()
            col.button.side_effect = (
                lambda label, **kwargs: bool(add and label == "Ajouter")
            )
            col.selectbox.side_effect = (
                lambda label, options, **kwargs: choices.get(label, list(options)[0])
            )
            col.number_input.side_effect = (
                lambda label, **kwargs: 10 if "Quantité (" in label else 150.0
            )
            col.date_input.return_value = "2026-12-01"
            out.append(col)
        col_sets.append(out)
        return out

    ui.st.columns.side_effect = columns
    return col_sets


def _quantity_and_price_calls(column_sets):
    for columns in column_sets:
        if len(columns) == 3 and any(
            "Quantité (" in str(call.args[0])
            for col in columns for call in col.number_input.call_args_list
        ):
            qty_call = columns[0].number_input.call_args
            price_call = columns[1].number_input.call_args
            add_call = columns[2].button.call_args
            return qty_call, price_call, add_call
    raise AssertionError("Saisie de commande introuvable")


def test_piece_appears_in_card_quantity_price_and_preview(ui):
    sets = _configure_new_order(ui)
    ui.mod.show_achats_page()
    assert any("Fiche de l'article sélectionné" in str(c)
               for c in ui.st.markdown.call_args_list)
    writes = [c.args[0] for cols in sets for col in cols
              for c in col.write.call_args_list]
    assert "PCS" in writes
    assert "Carton" in writes
    qty, price, add = _quantity_and_price_calls(sets)
    assert qty.args[0] == "Quantité (PCS)"
    assert qty.kwargs["min_value"] == 1
    assert qty.kwargs["step"] == 1
    assert qty.kwargs["format"] == "%d"
    assert price.args[0] == "Prix unitaire (DZD/PCS)"
    assert add.kwargs["disabled"] is False
    assert any("1,500.00 DZD" in str(c) for c in ui.st.caption.call_args_list)
    assert ui.st.session_state[ui.mod._cart_key("USR-1")] == []


def test_adding_article_keeps_unit_and_amount_in_order_basket(ui):
    sets = _configure_new_order(ui, add=True)
    ui.mod.show_achats_page()
    assert len(ui.st.session_state[ui.mod._cart_key("USR-1")]) == 1
    line = ui.st.session_state[ui.mod._cart_key("USR-1")][0]
    assert line["mp_id"] == "NG-EMB-BIDON-5L"
    assert line["unite_cond"] == "PCS"
    assert line["qte_cond"] == line["qte_totale"] == 10
    assert line["prix_unitaire"] == 150.0
    assert Decimal(str(line["total_devise"])) == Decimal("1500")
    # Les colonnes d'affichage changent, mais pas le schéma de la RPC.
    df = ui.st.dataframe.call_args.args[0]
    assert "Unité de stock" in df.columns
    assert df.iloc[0]["Unité de stock"] == "PCS"
    assert ui.achats.create_commande_achat.call_count == 0


def test_missing_unit_disables_add_without_substituting_fake_unit(ui):
    sets = _configure_new_order(ui, unit="", add=True)
    ui.mod.show_achats_page()
    qty, price, add = _quantity_and_price_calls(sets)
    assert add.kwargs["disabled"] is True
    assert qty.kwargs["disabled"] is True
    assert price.kwargs["disabled"] is True
    assert any("Unité de stock absente" in str(c)
               for c in ui.st.warning.call_args_list)
    assert ui.st.session_state[ui.mod._cart_key("USR-1")] == []


def test_litre_uses_decimal_quantity_without_inventing_package(ui):
    sets = _configure_new_order(ui, unit="L", packaging="")
    ui.mod.show_achats_page()
    qty, price, add = _quantity_and_price_calls(sets)
    assert qty.args[0] == "Quantité (L)"
    assert qty.kwargs["min_value"] == 0.001
    assert qty.kwargs["step"] == 0.001
    assert qty.kwargs["format"] == "%.3f"
    assert price.args[0] == "Prix unitaire (DZD/L)"
    writes = [c.args[0] for cols in sets for col in cols
              for c in col.write.call_args_list]
    assert "Non renseigné" in writes
    assert add.kwargs["disabled"] is False


def test_reference_ambiguity_blocks_addition(ui):
    sets = _configure_new_order(ui, add=True)
    ref = ui.mod.get_mp_actives.return_value
    ui.mod.get_mp_actives.return_value = pd.concat([ref, ref], ignore_index=True)
    ui.mod.show_achats_page()
    assert any("ambiguë" in str(c) for c in ui.st.error.call_args_list)
    assert ui.st.session_state[ui.mod._cart_key("USR-1")] == []


def test_unit_normalization_avoids_fractional_pieces(ui):
    assert ui.mod._unite_stock_comptee("Pièces")
    assert ui.mod._unite_stock_comptee("PCE")
    assert ui.mod._unite_stock_comptee("Unité")
    assert not ui.mod._unite_stock_comptee("L")
    assert not ui.mod._unite_stock_comptee("KG")
    assert ui.mod._catalogue_achat_texte(None) == ""
    assert ui.mod._catalogue_achat_texte("  Bidon ") == "Bidon"


def test_purchase_order_pdf_uses_recorded_unit_not_changed_catalogue():
    from modules.documents.erp_print import (
        load_operation_snapshot, render_operation_pdf,
    )
    data = {
        ("commandes_achats", "commande_achat_id", "CMA-1"): [{
            "commande_achat_id": "CMA-1", "fournisseur_id": "FOU-1",
            "date_commande": "2026-11-23", "statut": "EN_ATTENTE",
            "montant_total_local": "1500",
        }],
        ("fournisseurs", "fournisseur_id", "FOU-1"): [{
            "fournisseur_id": "FOU-1", "nom": "Fournisseur test",
        }],
        ("lignes_achats", "commande_achat_id", "CMA-1"): [{
            "ligne_achat_id": "LAC-1", "commande_achat_id": "CMA-1",
            "mp_id": "NG-EMB-BIDON-5L",
            "unite_cond": "PCS", "qte_totale": "10",
            "prix_unitaire": "150", "total_devise": "1500",
        }],
        ("matieres_premieres", "mp_id", "NG-EMB-BIDON-5L"): [{
            "mp_id": "NG-EMB-BIDON-5L", "nom": "Bidon 5L",
            "unite_stock": "UNITES",  # référentiel modifié après la commande
        }],
    }

    def read(table, *, equal_column, equal_value, max_rows):
        return data.get((table, equal_column, equal_value), [])

    snapshot = load_operation_snapshot("Commande fournisseur", "CMA-1", reader=read)
    assert snapshot["lines"][0]["unite"] == "PCS"
    assert render_operation_pdf(snapshot).startswith(b"%PDF")
