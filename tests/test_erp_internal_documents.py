"""Tests des copies internes Finance/Stocks/RH, sans Supabase ni mutation."""
from __future__ import annotations

import pytest

from modules.documents.internal_print import (
    InternalPrintError, INTERNAL_KINDS, load_internal_snapshot,
    render_internal_pdf,
)


RECORDS = {
    "Accusé interne d'encaissement": {
        "recu_id": "RINT-1", "reglement_id": "REG-1",
        "client_id": "CLI-1", "date_reglement": "2026-11-23",
        "montant_encaisse": "1500.25", "mode_paiement": "Virement",
        "reference_reglement": "REF-1", "statut": "INTERNE_NON_FISCAL",
        "timbre_statut": "NON_CALCULE",
    },
    "Demande de congé": {
        "demande_conge_id": "CNG-1", "employe_id": "EMP-1",
        "date_debut": "2026-11-25", "date_fin": "2026-11-30",
        "motif": "Congé annuel", "statut": "EN_ATTENTE",
    },
    "Fiche de mouvement MP": {
        "mouvement_id": "MVT-1", "date": "2026-11-23",
        "type_mouvement": "ENTREE", "mp_id": "MP-1",
        "quantite": "40.25", "reference": "BR-1", "lot_id": "LOT-1",
        "prix_entree": "18.35",
    },
    "Fiche de mouvement PF": {
        "mouvement_pf_id": "MVTPF-1", "date": "2026-11-23",
        "type_mouvement": "SORTIE", "sku_id": "SKU-1",
        "quantite": "12", "reference": "BL-1", "lot_id": "LOT-2",
        "cout_unitaire": "10",
    },
}


def reader_for(kind, row, calls):
    table, key, _ = INTERNAL_KINDS[kind]
    def reader(actual_table, *, equal_column, equal_value, max_rows):
        calls.append((actual_table, equal_column, equal_value, max_rows))
        assert (actual_table, equal_column, max_rows) == (table, key, 2)
        return [dict(row)]
    return reader


@pytest.mark.parametrize("kind", list(RECORDS))
def test_all_internal_kinds_read_one_strict_record(kind):
    calls = []
    row = RECORDS[kind]
    identifier = next(iter(row.values()))
    snapshot = load_internal_snapshot(
        kind, identifier, reader=reader_for(kind, row, calls),
    )
    assert snapshot["id"] == identifier
    assert len(calls) == 1
    assert snapshot["warning"] and snapshot["fields"]
    assert snapshot["source"] == INTERNAL_KINDS[kind][0]
    assert snapshot["date"].startswith("2026-")


@pytest.mark.parametrize("kind", list(RECORDS))
def test_internal_kinds_render_valid_pdf(kind):
    row = RECORDS[kind]
    identifier = next(iter(row.values()))
    snapshot = load_internal_snapshot(
        kind, identifier, reader=reader_for(kind, row, []),
    )
    data = render_internal_pdf(snapshot)
    assert isinstance(data, bytes) and data.startswith(b"%PDF")
    assert 1000 < len(data) < 1_500_000


@pytest.mark.parametrize("kind", list(RECORDS))
def test_missing_document_must_fail_closed(kind):
    identifier = next(iter(RECORDS[kind].values()))
    table, pk, _ = INTERNAL_KINDS[kind]
    with pytest.raises(InternalPrintError):
        load_internal_snapshot(
            kind, identifier, reader=lambda *args, **kwargs: [],
        )
    with pytest.raises(InternalPrintError):
        load_internal_snapshot(
            kind, identifier, reader=lambda *args, **kwargs: [
                {pk: identifier}, {pk: identifier}],
        )


@pytest.mark.parametrize("bad", ["", "<script>", "RINT 1", "../RINT", "A" * 130, None])
def test_invalid_reference_never_reads(bad):
    def forbidden(*args, **kwargs):
        raise AssertionError("Le serveur ne doit pas être interrogé")
    with pytest.raises(InternalPrintError):
        load_internal_snapshot(
            "Accusé interne d'encaissement", bad, reader=forbidden,
        )


@pytest.mark.parametrize("bad_field,bad_value", [
    ("statut", "VALIDE"), ("timbre_statut", "CALCULE"),
    ("montant_encaisse", -1), ("montant_encaisse", None),
    ("montant_encaisse", "NaN"), ("client_id", ""),
    ("date_reglement", "pas-une-date"),
])
def test_invalid_internal_receipt_cannot_be_printed(bad_field, bad_value):
    row = {**RECORDS["Accusé interne d'encaissement"], bad_field: bad_value}
    with pytest.raises(InternalPrintError):
        load_internal_snapshot(
            "Accusé interne d'encaissement", "RINT-1",
            reader=reader_for("Accusé interne d'encaissement", row, []),
        )


def test_inverse_leave_dates_are_refused():
    row = {**RECORDS["Demande de congé"], "date_fin": "2026-11-20"}
    with pytest.raises(InternalPrintError):
        load_internal_snapshot(
            "Demande de congé", "CNG-1",
            reader=reader_for("Demande de congé", row, []),
        )


def test_no_official_documents_or_mutations_in_pdf_engine():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    content = (root / "modules/documents/internal_print.py").read_text()
    assert ".rpc(" not in content
    assert ".insert(" not in content
    assert ".update(" not in content
    assert ".delete(" not in content
    assert "NON FISCAL" in content
    assert "NON SIGNÉE" in content
    assert "Ne vaut pas autorisation" in content


def test_all_three_modules_use_row_actions():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for module, required in [
        ("finance", "kind=\"Accusé interne d'encaissement\""),
        ("rh", 'kind="Demande de congé"'),
        ("stocks", 'kind="Fiche de mouvement MP"'),
    ]:
        code = (root / "modules" / module / "views.py").read_text()
        assert "show_recorded_documents(" in code
        assert required in code
    stock_code = (root / "modules/stocks/views.py").read_text()
    assert 'kind="Fiche de mouvement PF"' in stock_code
    assert 'st.session_state.get(history_key)' in stock_code
