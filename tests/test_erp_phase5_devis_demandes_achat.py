"""Phase 5 : devis commercial enregistré et DA-062 strictement non active.

Tests 100 % hors réseau et sans mutation.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from modules.documents.erp_print import (
    KINDS, OperationPrintError, load_operation_snapshot, render_operation_pdf,
)
from modules.achats.request_print import (
    RequestPrintError, build_request_snapshot, load_request_snapshot,
)
from modules.documents.internal_print import INTERNAL_KINDS, render_internal_pdf

ROOT = Path(__file__).resolve().parents[1]


def _quote_data():
    return {
        ("devis", "devis_id", "DEV-1"): [{
            "devis_id": "DEV-1", "client_id": "CLI-1",
            "date": "2026-11-23", "validite": "2026-12-23",
            "statut": "BROUILLON", "commercial_id": "USR-1",
        }],
        ("lignes_devis", "devis_id", "DEV-1"): [{
            "ligne_devis_id": "LD-1", "devis_id": "DEV-1",
            "sku_id": "SKU-1", "quantite": "3",
            "prix_unitaire": "100", "remise_pct": "5",
        }],
        ("clients", "client_id", "CLI-1"): [{
            "client_id": "CLI-1", "nom": "Client enregistré",
        }],
        ("sku_conditionnement", "sku_id", "SKU-1"): [{
            "sku_id": "SKU-1", "pf_id": "PF-1", "format": "Sac 25 kg",
            "unite_vente": "SAC",
        }],
        ("produits", "pf_id", "PF-1"): [{
            "pf_id": "PF-1", "nom": "Mortier test",
        }],
    }


def _reader(data):
    def get(table, *, equal_column, equal_value, max_rows):
        assert max_rows in (2, 200)
        return data.get((table, equal_column, equal_value), [])
    return get


def test_quotation_pdf_uses_persisted_prices_discounts_without_fake_total():
    assert "Devis commercial" in KINDS
    snapshot = load_operation_snapshot(
        "Devis commercial", "DEV-1", reader=_reader(_quote_data()))
    assert snapshot["partner"] == "Client enregistré"
    assert snapshot["lines"][0]["prix_unitaire"] == "100"
    assert snapshot["lines"][0]["quantite"] == "3"
    assert "5 %" in snapshot["lines"][0]["designation"]
    assert snapshot["lines"][0]["total_ht"] == ""
    assert snapshot["totals"] == []
    assert "NON ÉMISE" in snapshot["warning"]
    assert render_operation_pdf(snapshot).startswith(b"%PDF")


@pytest.mark.parametrize("discount", ["NaN", "-1", "101", True])
def test_quote_bad_discount_fails_closed(discount):
    data = _quote_data()
    data[("lignes_devis", "devis_id", "DEV-1")][0]["remise_pct"] = discount
    with pytest.raises((ValueError, OperationPrintError)):
        load_operation_snapshot("Devis commercial", "DEV-1", reader=_reader(data))


def _request_data(status="BROUILLON", *, motivation=None):
    return [{
        "demande_id": "DA-1", "demandeur_id": "USR-1",
        "motivation": motivation or "Motivation documentée pour le projet technique",
        "date_souhaitee": "2026-12-23",
        "cree_le": "2026-11-23T12:00:00+00:00",
        "statut": status, "approbateur_id": "USR-2" if status in ("APPROUVEE","COMMANDEE") else None,
        "decision_motif": "Contrôlé", "commande_achat_id": "CMA-1" if status == "COMMANDEE" else None,
    }]


def _request_lines():
    return [{"mp_id": "MP-1", "unite_stock": "KG", "quantite": "50.25"}]


def test_da_copy_from_recorded_source_is_readonly():
    snap = build_request_snapshot("DA-1", _request_data(), _request_lines())
    assert snap["kind"] in INTERNAL_KINDS
    assert snap["id"] == "DA-1"
    assert snap["date"] == "2026-11-23"
    assert snap["fields"][-1][1] == "MP-1 — 50.25 KG"
    assert "NON SIGNÉE" in snap["warning"]
    assert render_internal_pdf(snap).startswith(b"%PDF")


@pytest.mark.parametrize("status", ["SOUMISE", "APPROUVEE", "COMMANDEE", "REFUSEE"])
def test_da_copy_reflects_real_status_without_approval(status):
    snap = build_request_snapshot("DA-1", _request_data(status), _request_lines())
    assert ("Statut enregistré", status) in snap["fields"]
    assert "Aucune" not in snap["warning"]
    assert "Approbation indépendante" in snap["warning"]


def test_da_print_disabled_without_flag_before_any_remote_read(monkeypatch):
    monkeypatch.delenv("ERP_PURCHASE_REQUESTS_ENABLED", raising=False)
    with pytest.raises(RequestPrintError, match="désactivé"):
        load_request_snapshot("DA-1")


@pytest.mark.parametrize("bad_lines", [
    [], [{"mp_id": "MP-1", "unite_stock": "", "quantite": 2}],
    [{"mp_id": "MP-1", "unite_stock": "KG", "quantite": 0}],
    [{"mp_id": "MP-1", "unite_stock": "KG", "quantite": "NaN"}],
    _request_lines() + _request_lines(),
])
def test_bad_da_lines_cannot_make_a_pdf(bad_lines):
    with pytest.raises(RequestPrintError):
        build_request_snapshot("DA-1", _request_data(), bad_lines)


def test_foreign_da_is_rejected_before_loading_lines(monkeypatch):
    import modules.achats.requisitions as req
    monkeypatch.setenv("ERP_PURCHASE_REQUESTS_ENABLED", "1")
    monkeypatch.setattr(req, "list_purchase_requests", lambda: _request_data())
    def forbidden(_):
        raise AssertionError("Aucune lecture de lignes d'une demande étrangère")
    monkeypatch.setattr(req, "purchase_request_lines", forbidden)
    with pytest.raises(RequestPrintError):
        load_request_snapshot("DA-OTHER")


def test_self_approved_da_must_not_print():
    rows = _request_data("APPROUVEE")
    rows[0]["approbateur_id"] = rows[0]["demandeur_id"]
    with pytest.raises(RequestPrintError, match="Auto-approbation"):
        build_request_snapshot("DA-1", rows, _request_lines())


def test_complete_motivation_kept_on_pdf():
    motivation = "Besoin " * 214 + "BB"  # 1500 caractères de justification
    snap = build_request_snapshot("DA-1", _request_data(motivation=motivation), _request_lines())
    assert motivation in dict(snap["fields"])["Motivation enregistrée (intégrale)"]
    data = render_internal_pdf(snap)
    assert data.startswith(b"%PDF")


def test_erp62_gate_not_changed_and_no_sql_mutations():
    achats = (ROOT / "modules/achats/views.py").read_text()
    quotes = (ROOT / "modules/ventes/views.py").read_text()
    req_view = (ROOT / "modules/achats/requisitions_views.py").read_text()
    printing = (ROOT / "modules/achats/request_print.py").read_text()
    assert 'os.environ.get("ERP_PURCHASE_REQUESTS_ENABLED") == "1"' in achats
    assert 'if demandes_actives and active_panel == panels[3]:' in achats
    assert "kind=\"Demande d'achat (copie interne)\"" in req_view
    assert 'kind="Devis commercial"' in quotes
    assert '"devis", page=int(page_devis)' in quotes
    assert ".rpc(" not in printing
    assert ".update(" not in printing
    assert ".insert(" not in printing
    assert ".delete(" not in printing
