"""Phase 4 : impressions consultatives des factures fournisseurs et rapports de production.

Contrôles sans connexion ni écriture Supabase.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modules.documents.erp_print import (
    KINDS, OperationPrintError, load_operation_snapshot, render_operation_pdf,
)
from modules.documents.internal_print import (
    INTERNAL_KINDS, InternalPrintError, load_internal_snapshot, render_internal_pdf,
)


KIND_FF = "Facture fournisseur (aperçu interne)"


def _supplier_data():
    return {
        ("factures_fournisseurs", "facture_fournisseur_id", "FF-1"): [{
            "facture_fournisseur_id": "FF-1", "commande_achat_id": "CA-1",
            "fournisseur_id": "FOU-1", "date": "2026-11-23",
            "reference_facture_fournisseur": "F-2026-17",
            "montant_ht": "1000", "montant_tva": "190",
            "montant_ttc": "1190", "taux_tva": "19",
            "statut_paiement": "NON_PAYEE",
        }],
        ("commandes_achats", "commande_achat_id", "CA-1"): [{
            "commande_achat_id": "CA-1", "fournisseur_id": "FOU-1",
        }],
        ("fournisseurs", "fournisseur_id", "FOU-1"): [{
            "fournisseur_id": "FOU-1", "nom": "Fournisseur test",
        }],
        ("lignes_factures_fournisseurs", "facture_fournisseur_id", "FF-1"): [{
            "ligne_ff_id": "FFL-1", "facture_fournisseur_id": "FF-1",
            "mp_id_ou_service": "SERVICE-TRANSPORT",
            "quantite": "2", "prix_unitaire": "500", "total_ht": "1000",
            "taux_tva": "19",
        }],
    }


def _reader(data, calls):
    def read(table, *, equal_column, equal_value, max_rows):
        calls.append((table, equal_column, equal_value, max_rows))
        assert 0 < max_rows <= 200
        return data.get((table, equal_column, equal_value), [])
    return read


def test_supplier_invoice_uses_recorded_service_without_inventing_material():
    calls = []
    snapshot = load_operation_snapshot(
        KIND_FF, "FF-1", reader=_reader(_supplier_data(), calls),
    )
    assert KIND_FF in KINDS
    assert snapshot["id"] == "FF-1"
    assert snapshot["partner"] == "Fournisseur test"
    assert snapshot["lines"][0]["reference"] == "SERVICE-TRANSPORT"
    assert snapshot["lines"][0]["unite"] == ""
    assert snapshot["lines"][0]["total_ht"] == "1000"
    assert snapshot["totals"][1][1] == "190"
    assert "NON VALABLE FISCALEMENT" in snapshot["warning"]
    assert render_operation_pdf(snapshot).startswith(b"%PDF")
    assert not any(row[0] == "matieres_premieres" for row in calls)


def test_supplier_mismatch_fails_closed():
    data = _supplier_data()
    data[("commandes_achats", "commande_achat_id", "CA-1")][0]["fournisseur_id"] = "FOU-AUTRE"
    with pytest.raises(OperationPrintError):
        load_operation_snapshot(KIND_FF, "FF-1", reader=_reader(data, []))


def test_supplier_invoice_missing_lines_fails_closed():
    data = _supplier_data()
    data[("lignes_factures_fournisseurs", "facture_fournisseur_id", "FF-1")] = []
    with pytest.raises(OperationPrintError):
        load_operation_snapshot(KIND_FF, "FF-1", reader=_reader(data, []))


@pytest.mark.parametrize("kind,pk,id_value,row", [
    ("Fiche de consommation OF", "consommation_id", "CONSO-1", {
        "consommation_id": "CONSO-1", "of_id": "OF-1", "mp_id": "MP-1",
        "lot_id": "LOT-1", "quantite_consommee": "13.25",
    }),
    ("Compte rendu de contrôle qualité", "qc_id", "QC-1", {
        "qc_id": "QC-1", "of_id": "OF-1",
        "date": "2026-11-23", "conforme": "OUI",
        "controleur": "Opérateur test", "remarques": "RAS",
    }),
])
def test_production_registered_records_make_no_fake_certificate(kind, pk, id_value, row):
    assert kind in INTERNAL_KINDS
    table = INTERNAL_KINDS[kind][0]
    calls = []
    snapshot = load_internal_snapshot(
        kind, id_value, reader=_reader({(table, pk, id_value): [row]}, calls)
    )
    assert calls == [(table, pk, id_value, 2)]
    assert snapshot["partner"] == "OF-1"
    assert "NON SIGNÉE" in snapshot["warning"]
    assert render_internal_pdf(snapshot).startswith(b"%PDF")
    if kind == "Fiche de consommation OF":
        assert snapshot["date"] == "NON ENREGISTRÉE DANS LE REGISTRE"
        assert snapshot["date_label"] == "Date du mouvement de consommation"


def test_production_invalid_quantity_and_missing_controller_refused():
    key = "Fiche de consommation OF"
    row = {"consommation_id": "CONSO-1", "of_id": "OF-1", "mp_id": "MP-1",
           "quantite_consommee": "NaN"}
    with pytest.raises(InternalPrintError):
        load_internal_snapshot(
            key, "CONSO-1", reader=_reader({
                ("consommations_of", "consommation_id", "CONSO-1"): [row],
            }, []))
    row = {"qc_id": "QC-1", "of_id": "OF-1",
           "date": "2026-11-23", "conforme": "OUI", "controleur": ""}
    with pytest.raises(InternalPrintError):
        load_internal_snapshot(
            "Compte rendu de contrôle qualité", "QC-1",
            reader=_reader({("controle_qualite", "qc_id", "QC-1"): [row]}, []),
        )


def test_three_modules_wired_without_new_mutations():
    root = Path(__file__).resolve().parents[1]
    achat = (root / "modules/achats/views.py").read_text()
    production = (root / "modules/production/views.py").read_text()
    stocks = (root / "modules/stocks/views.py").read_text()
    assert 'kind="Facture fournisseur (aperçu interne)"' in achat
    assert 'id_column="facture_fournisseur_id"' in achat
    assert 'kind="Fiche de consommation OF"' in production
    assert 'kind="Compte rendu de contrôle qualité"' in production
    assert 'show_report_actions(' in stocks
    assert 'st.session_state.get(state_key)' in stocks
    assert 'production_history_loaded_' in production
