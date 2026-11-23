"""ERP-063 : rapprochement BC/BR/Facture fail-closed sans paiement."""
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pytest

from modules.achats.three_way_match import (
    ThreeWayError, load_supplier_invoice_match, reconcile_supplier_invoice,
)


ROOT = Path(__file__).resolve().parents[1]


def _documents():
    invoice = {
        "facture_fournisseur_id": "FF-TEST", "commande_achat_id": "PO-TEST",
        "fournisseur_id": "FOU-TEST", "statut_paiement": "NON_PAYEE",
        "montant_ht": "400", "montant_tva": "0", "montant_ttc": "400",
    }
    order = {
        "commande_achat_id": "PO-TEST", "fournisseur_id": "FOU-TEST",
        "devise": "DZD", "taux_change": "1", "statut": "PARTIELLEMENT_RECEPTIONNE",
    }
    ordered = [
        {"commande_achat_id": "PO-TEST", "mp_id": "MP-TEST",
         "qte_totale": "10", "prix_unitaire": "100", "total_devise": "1000"}
    ]
    receipts = [
        {"bon_reception_id": "BR-TEST", "commande_achat_id": "PO-TEST",
         "controle_conformite": "OUI"},
    ]
    received = [
        {"ligne_br_id": "LBR-TEST", "bon_reception_id": "BR-TEST",
         "mp_id": "MP-TEST", "quantite_recue": "4"},
    ]
    billed = [
        {"facture_fournisseur_id": "FF-TEST", "mp_id_ou_service": "MP-TEST",
         "quantite": "4", "prix_unitaire": "100", "total_ht": "400"}
    ]
    siblings = [(invoice, billed)]
    return invoice, order, ordered, receipts, received, billed, siblings


def _match(docs):
    return reconcile_supplier_invoice(*docs)


def test_partial_receipt_and_invoice_concordant_but_never_payable():
    result = _match(_documents())
    assert result["verdict"] == "CONCORDANCE_DOCUMENTAIRE"
    assert result["lignes"][0]["quantite_bc"] == "10"
    assert result["lignes"][0]["quantite_recue_conforme"] == "4"
    assert result["lignes"][0]["quantite_facture"] == "4"
    assert result["autorise_paiement"] is False
    assert result["certification_fiscale"] is False
    assert result["ecriture_stock"] is False
    assert result["instantane_transactionnel"] is False
    assert result["observations"]


def test_draft_supplier_invoice_stays_blocked_even_if_balanced():
    d = _documents()
    d[0]["statut_paiement"] = "BROUILLON"
    assert any("Statut facture" in s for s in _match(d)["blocages"])


@pytest.mark.parametrize("field", ["montant_tva", "montant_ttc"])
def test_missing_tax_information_refuses_verdict(field):
    docs = _documents()
    docs[0][field] = None
    result = _match(docs)
    assert result["verdict"] == "ECARTS_OU_PIECES_MANQUANTES"
    assert any("TVA ou TTC" in s for s in result["blocages"])


def test_invoice_quantity_beyond_compliant_receipts_is_blocked():
    docs = _documents()
    docs[5][0]["quantite"] = "5"
    docs[5][0]["total_ht"] = "500"
    docs[0]["montant_ht"] = docs[0]["montant_ttc"] = "500"
    assert any("supérieure aux réceptions" in s for s in _match(docs)["blocages"])


def test_cumulative_other_invoices_prevents_double_billing():
    docs = _documents()
    other_invoice = {
        "facture_fournisseur_id": "FF-OTHER", "commande_achat_id": "PO-TEST",
        "fournisseur_id": "FOU-TEST", "statut_paiement": "BROUILLON",
    }
    other_lines = [{
        "facture_fournisseur_id": "FF-OTHER", "mp_id_ou_service": "MP-TEST",
        "quantite": "7", "prix_unitaire": "100", "total_ht": "700",
    }]
    docs[6].append((other_invoice, other_lines))
    result = _match(docs)
    assert result["lignes"][0]["quantite_facturee_cumulee"] == "11"
    assert any("cumulée" in s for s in result["blocages"])


def test_supplier_mismatch_and_foreign_po_reference_are_detected():
    docs = _documents()
    docs[0]["fournisseur_id"] = "OTHER"
    result = _match(docs)
    assert any("Fournisseur facture" in message for message in result["blocages"])
    docs[0]["commande_achat_id"] = "DIFFERENT"
    with pytest.raises(ThreeWayError, match="autre commande"):
        _match(docs)


def test_nonconform_receipt_cannot_cover_invoice():
    docs = _documents()
    docs[3][0]["controle_conformite"] = "NON"
    result = _match(docs)
    assert result["lignes"][0]["quantite_recue_conforme"] == "0"
    assert any("non conforme" in s for s in result["blocages"])


def test_po_currency_other_than_dzd_does_not_fake_conversion():
    docs = _documents()
    docs[1]["devise"] = "EUR"
    assert any("Devise" in s for s in _match(docs)["blocages"])


def test_unit_price_mismatch_blocks_invoice():
    docs = _documents()
    docs[5][0]["prix_unitaire"] = "110"
    docs[5][0]["total_ht"] = "440"
    docs[0]["montant_ht"] = docs[0]["montant_ttc"] = "440"
    assert any("Prix facture" in s for s in _match(docs)["blocages"])


def test_wrong_line_ht_fails_closed_before_report():
    docs = _documents()
    docs[5][0]["total_ht"] = "401"
    with pytest.raises(ThreeWayError):
        _match(docs)


@pytest.mark.parametrize("value", [None, "-1", "NaN", "Infinity", True, "1e20"])
def test_wrong_quantities_fail_closed(value):
    docs = _documents()
    docs[5][0]["quantite"] = value
    with pytest.raises(ThreeWayError):
        _match(docs)


def test_incomplete_sibling_listing_fails_closed():
    docs = _documents()
    docs[6].clear()
    with pytest.raises(ThreeWayError):
        _match(docs)


def test_no_invoice_lines_fails_closed():
    docs = _documents()
    docs[5].clear()
    with pytest.raises(ThreeWayError):
        _match(docs)


def test_real_read_strict_loader_only_reads_six_tables_no_mutation():
    documents = _documents()
    inv, po, polines, brs, brlines, ilines, _ = documents
    data = {
        ("factures_fournisseurs", "facture_fournisseur_id", "FF-TEST"): [inv],
        ("commandes_achats", "commande_achat_id", "PO-TEST"): [po],
        ("lignes_achats", "commande_achat_id", "PO-TEST"): polines,
        ("bons_reception", "commande_achat_id", "PO-TEST"): brs,
        ("lignes_bons_reception", "bon_reception_id", "BR-TEST"): brlines,
        ("lignes_factures_fournisseurs", "facture_fournisseur_id", "FF-TEST"): ilines,
        ("factures_fournisseurs", "commande_achat_id", "PO-TEST"): [inv],
    }
    calls = []
    def reader(table, *, equal_column, equal_value, max_rows):
        calls.append((table, equal_column, equal_value, max_rows))
        return deepcopy(data.get((table, equal_column, equal_value), []))
    assert load_supplier_invoice_match("FF-TEST", reader=reader)["verdict"] == \
        "CONCORDANCE_DOCUMENTAIRE"
    assert len(calls) == 8
    assert all(0 < limit <= 200 for _, _, _, limit in calls)


def test_read_error_never_creates_fake_concordance():
    def denied(*args, **kwargs):
        raise PermissionError("No rights")
    with pytest.raises(PermissionError):
        load_supplier_invoice_match("FF-TEST", reader=denied)


def test_ui_in_achats_history_and_exports_consultative_only():
    code = (ROOT / "modules/achats/views.py").read_text()
    panel = (ROOT / "modules/achats/three_way_views.py").read_text()
    row_actions = (ROOT / "modules/achats/po_row_actions.py").read_text()
    assert 'if active_panel == panels[2]:' in code
    assert "show_three_way_match" in code
    assert "show_purchase_orders_with_actions(rows_commandes, user_id)" in code
    assert "show_po_print_copy" not in code  # la référence n'est plus saisie à la main
    assert "load_operation_snapshot" in row_actions
    assert "render_operation_pdf(snapshot)" in row_actions
    assert "NON ÉMISE" in row_actions
    assert "load_supplier_invoice_match" in panel
    assert "autorise_paiement" not in panel  # aucun bouton d'autorisation
    assert "build_export(" in panel
    assert "NON PAYABLE" in panel
