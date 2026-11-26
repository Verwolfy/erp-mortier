"""ERP-054 — Documents imprimables reliés à des opérations, sans émission."""
import pytest

from modules.documents.erp_print import (
    KINDS, OperationPrintError, load_operation_snapshot, render_operation_pdf,
)


def _reader(data):
    def read(table, *, equal_column, equal_value, max_rows):
        assert max_rows in (2, 200)
        return data.get((table, equal_column, equal_value), [])
    return read


def _catalog():
    return {
        ("sku_conditionnement", "sku_id", "SKU-1"): [
            {"sku_id": "SKU-1", "pf_id": "PF-1", "format": "Sac 5 kg", "unite_vente": "SAC"}],
        ("produits", "pf_id", "PF-1"): [{"pf_id": "PF-1", "nom": "Mortier test"}],
        ("clients", "client_id", "CL-1"): [{"client_id": "CL-1", "nom": "Client de test"}],
        ("matieres_premieres", "mp_id", "MP-1"): [
            {"mp_id": "MP-1", "nom": "Ciment test", "unite_stock": "KG"}],
        ("fournisseurs", "fournisseur_id", "FR-1"): [
            {"fournisseur_id": "FR-1", "nom": "Fournisseur de test"}],
    }


def test_of_print_uses_real_planned_sku_without_recipe_invention():
    data = _catalog()
    data[("ordres_fabrication", "of_id", "OF-1")] = [{
        "of_id": "OF-1", "sku_id": "SKU-1", "pf_id": "PF-1",
        "recette_id": "REC-1", "quantite_prevue": "12",
        "quantite_produite": "0", "date_planification": "2026-11-01",
        "statut": "PLANIFIE", "notes": "Essai",
    }]
    snapshot = load_operation_snapshot("Ordre de fabrication", "OF-1", reader=_reader(data))
    assert snapshot["lines"][0]["quantite"] == "12"
    assert snapshot["lines"][0]["prix_unitaire"] == ""
    assert "NON SIGNÉE" in snapshot["warning"]
    assert render_operation_pdf(snapshot).startswith(b"%PDF")


def test_bl_print_uses_actual_delivery_quantities_and_lot():
    data = _catalog()
    data[("bons_livraison", "bl_id", "BL-1")] = [{
        "bl_id": "BL-1", "commande_vente_id": "CV-1",
        "date": "2026-11-02", "statut": "EXPEDIE", "transporteur": "Interne",
    }]
    data[("commandes_ventes", "commande_vente_id", "CV-1")] = [{
        "commande_vente_id": "CV-1", "client_id": "CL-1", "statut": "LIVREE",
    }]
    data[("lignes_bons_livraison", "bl_id", "BL-1")] = [{
        "bl_id": "BL-1", "sku_id": "SKU-1", "quantite_livree": "3",
        "lot_id": "LOT-2",
    }]
    snapshot = load_operation_snapshot("Bon de livraison", "BL-1", reader=_reader(data))
    assert snapshot["lines"][0]["quantite"] == "3"
    assert snapshot["lines"][0]["lot"] == "LOT-2"
    assert snapshot["partner"] == "Client de test"
    assert render_operation_pdf(snapshot).startswith(b"%PDF")


def test_invoice_preview_keeps_persisted_taxes_and_discounts():
    data = _catalog()
    data[("factures", "facture_id", "FAC-1")] = [{
        "facture_id": "FAC-1", "client_id": "CL-1", "date": "2026-11-03",
        "statut": "VALIDE", "type_facture": "FactureClient",
        "montant_ht": "190", "montant_tva": "36.1",
        "montant_timbre": "0", "montant_ttc": "226.1",
    }]
    data[("lignes_facture", "facture_id", "FAC-1")] = [{
        "facture_id": "FAC-1", "sku_id": "SKU-1", "quantite": "2",
        "prix_unitaire": "100", "remise_ligne": "10", "total_ligne_ht": "190",
    }]
    snapshot = load_operation_snapshot("Facture (aperçu interne)", "FAC-1", reader=_reader(data))
    assert snapshot["totals"][1][1] == "36.1"
    assert snapshot["lines"][0]["total_ht"] == "190"
    assert "remise :" in snapshot["lines"][0]["designation"]
    assert "NON VALABLE FISCALEMENT" in snapshot["warning"]
    assert render_operation_pdf(snapshot).startswith(b"%PDF")


def test_receipt_print_uses_actual_received_quantity():
    data = _catalog()
    data[("bons_reception", "bon_reception_id", "BR-1")] = [{
        "bon_reception_id": "BR-1", "commande_achat_id": "CA-1",
        "date_reception": "2026-11-04", "controle_conformite": "OUI",
    }]
    data[("commandes_achats", "commande_achat_id", "CA-1")] = [{
        "commande_achat_id": "CA-1", "fournisseur_id": "FR-1",
        "date_commande": "2026-11-02", "statut": "RECEPTIONNE",
    }]
    data[("lignes_bons_reception", "bon_reception_id", "BR-1")] = [{
        "bon_reception_id": "BR-1", "mp_id": "MP-1", "quantite_recue": "4.5",
    }]
    snapshot = load_operation_snapshot("Bon de réception", "BR-1", reader=_reader(data))
    assert snapshot["lines"][0]["quantite"] == "4.5"
    assert snapshot["partner"] == "Fournisseur de test"


@pytest.mark.parametrize("kind", list(KINDS))
def test_unknown_reference_fails_closed(kind):
    with pytest.raises(OperationPrintError):
        load_operation_snapshot(kind, "ABSENT", reader=_reader({}))


def test_no_permission_is_never_replaced_by_empty_document():
    def forbidden(*args, **kwargs):
        raise PermissionError("refus")
    with pytest.raises(PermissionError):
        load_operation_snapshot("Bon de livraison", "BL-1", reader=forbidden)


@pytest.mark.parametrize("ref", ["", "a b", "../secret", "x" * 129])
def test_reference_validation_before_database_read(ref):
    def forbidden(*args, **kwargs):
        raise AssertionError("DB should not be read")
    with pytest.raises(OperationPrintError):
        load_operation_snapshot("Ordre de fabrication", ref, reader=forbidden)


def test_missing_invoice_line_does_not_generate_a_fake_invoice():
    data = _catalog()
    data[("factures", "facture_id", "FAC-1")] = [{
        "facture_id": "FAC-1", "client_id": "CL-1", "date": "2026-11-03",
    }]
    with pytest.raises(OperationPrintError):
        load_operation_snapshot("Facture (aperçu interne)", "FAC-1", reader=_reader(data))



def test_supplier_purchase_order_print_generates_branded_pdf_from_persisted_values():
    """Le document fournisseur doit être imprimable mais jamais marqué émis."""
    data = _catalog()
    data[("commandes_achats", "commande_achat_id", "E2E61-PO")] = [{
        "commande_achat_id": "E2E61-PO", "fournisseur_id": "FR-1",
        "date_commande": "2026-11-23", "statut": "EN_ATTENTE",
        "montant_total_local": "1000.00",
    }]
    data[("lignes_achats", "commande_achat_id", "E2E61-PO")] = [{
        "ligne_achat_id": "E2E61-L1", "commande_achat_id": "E2E61-PO",
        "mp_id": "MP-1", "unite_cond": "KG",
        "qte_cond": "10", "qte_totale": "10",
        "prix_unitaire": "100.00", "total_devise": "1000.00",
    }]
    snapshot = load_operation_snapshot(
        "Commande fournisseur", "E2E61-PO", reader=_reader(data),
    )
    assert snapshot["partner"] == "Fournisseur de test"
    assert snapshot["date"] == "2026-11-23"
    assert snapshot["lines"][0]["quantite"] == "10"
    assert snapshot["lines"][0]["prix_unitaire"] == "100.00"
    assert snapshot["lines"][0]["total_ht"] == "1000.00"
    assert snapshot["totals"] == [("Total", "1000.00")]
    assert "NON ÉMISE" in snapshot["warning"]
    pdf = render_operation_pdf(snapshot)
    assert pdf.startswith(b"%PDF")
    assert b"/Type /Page" in pdf
