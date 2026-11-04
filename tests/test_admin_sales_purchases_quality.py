"""Contrôles structuraux Achats/Ventes en lecture seule."""
import pytest

from modules.admin.sales_purchases_quality import (
    LINKS, HEADER_LINKS, TABLES, audit_sales_purchases, audit_sales_purchases_autorise,
)


def _data():
    data = {table: [] for table in TABLES}
    data.update({
        "clients": [],
        "fournisseurs": [{"fournisseur_id": "F1"}],
        "commandes_ventes": [{"commande_vente_id": "CV1"}],
        "commandes_achats": [{"commande_achat_id": "CA1"}],
        "sku_conditionnement": [{"sku_id": "SKU1"}],
        "matieres_premieres": [{"mp_id": "MP1"}],
        "lignes_commande_ventes": [
            {"commande_vente_id": "CV1", "sku_id": "SKU1", "quantite": "2"},
            {"commande_vente_id": "CV404", "sku_id": "SKU404", "quantite": "0"},
        ],
        "lignes_achats": [
            {"commande_achat_id": "CA1", "mp_id": "MP1", "qte_totale": "4"},
        ],
        "bons_livraison": [{"bl_id": "BL1", "commande_vente_id": "CV1"}],
        "lignes_bons_livraison": [
            {"bl_id": "BL1", "sku_id": "SKU1", "quantite_livree": "NaN"},
        ],
        "factures": [{"facture_id": "FA1", "commande_vente_id": ""}],
        "lignes_facture": [
            {"facture_id": "FA1", "sku_id": "SKU1", "quantite": "1"},
        ],
        "bons_reception": [{"bon_reception_id": "BR1", "commande_achat_id": "CA1"}],
        "lignes_bons_reception": [
            {"bon_reception_id": "BR1", "mp_id": "MP1", "quantite_recue": "3"},
        ],
        "factures_fournisseurs": [
            {"facture_fournisseur_id": "FF1", "commande_achat_id": "",
             "fournisseur_id": "F1"},
        ],
    })
    return data


def test_audit_flows_detecte_orphelins_et_quantites_sans_pii():
    rows = audit_sales_purchases(_data())
    assert len(rows) == len(LINKS) + len(HEADER_LINKS)
    assert rows[0]["Parents introuvables"] == 1
    assert rows[0]["Articles introuvables"] == 1
    assert rows[0]["Quantités non positives"] == 1
    assert rows[1]["Quantités invalides"] == 1
    assert rows[2]["Articles introuvables"] == 0
    # Les factures peuvent être créées hors commande.
    assert rows[6]["Parents manquants"] == 0
    assert rows[8]["Parents manquants"] == 0
    assert all("sku_id" not in row and "fournisseur_id" not in row for row in rows)


def test_audit_flows_refuse_lectures_partielles():
    data = _data()
    assert audit_sales_purchases_autorise(
        reader=lambda table: data[table]) == audit_sales_purchases(data)
    with pytest.raises(PermissionError):
        audit_sales_purchases_autorise(
            reader=lambda table: (_ for _ in ()).throw(PermissionError("Refus")))
    with pytest.raises(ValueError):
        audit_sales_purchases({**data, "lignes_achats": ["invalide"]})


def test_ui_audit_achats_ventes_aucune_ecriture():
    from pathlib import Path
    ui = Path("modules/admin/views.py").read_text(encoding="utf-8")
    service = Path("modules/admin/sales_purchases_quality.py").read_text(encoding="utf-8")
    assert "Analyser les flux Achats et Ventes autorisés" in ui
    assert "audit_sales_purchases_autorise()" in ui
    assert "fetch_data_paginated" in service
    assert "insert_hybrid" not in service and "update_hybrid" not in service
