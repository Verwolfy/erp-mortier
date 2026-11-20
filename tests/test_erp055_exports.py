"""ERP-055 : tests des trois formats, de la charte et des droits à l'export."""
from io import BytesIO
from pathlib import Path

import pytest

from core.export_catalogue import REPORTS, read_report
from core.export_formats import (
    ExportError, build_export, export_csv, export_excel, export_filename,
    export_pdf,
)


def _rows():
    return [
        {"reference": "SKU-00001", "désignation": "Mortier colle C1T — sac",
         "quantite": "2.5", "montant_dzd": "125.50",
         "commentaire": "=WEBSERVICE(\"https://example.invalid\")"},
        {"reference": "000123", "désignation": "Étanchéité", "quantite": "1",
         "montant_dzd": "50", "commentaire": "\t+cmd"},
    ]


FIELDS = ["reference", "désignation", "quantite", "montant_dzd", "commentaire"]


def test_csv_is_utf8_bom_semicolon_and_blocks_formula_injection():
    payload = export_csv(_rows(), FIELDS)
    assert payload.startswith(b"\xef\xbb\xbf")
    text = payload.decode("utf-8-sig")
    assert "référence" not in text
    assert "désignation;quantite;montant_dzd" in text
    assert "'=WEBSERVICE" in text
    assert "'\t+cmd" in text
    assert "SKU-00001" in text


def test_xlsx_has_corporate_palette_metadata_and_safe_cells():
    from openpyxl import load_workbook
    blob = export_excel(_rows(), FIELDS, title="Stock du mois",
                        warning="rapport non certifié")
    book = load_workbook(BytesIO(blob))
    sheet = book.active
    assert sheet["A1"].value.startswith("NEXTGEN | Stock du mois")
    assert sheet["A2"].value == "SARL NEXT GENRATION BUILDING SOLUTIONS"
    assert sheet["A3"].value.startswith("COPIE INTERNE")
    assert sheet["A5"].value == "reference"
    assert sheet["A5"].fill.fgColor.rgb.endswith("048B5B")
    assert sheet["D6"].value == 125.5
    assert sheet["E6"].value.startswith("'=WEBSERVICE")
    assert sheet["E6"].data_type != "f"
    assert sheet["E7"].value.startswith("'\t+cmd")
    assert sheet.freeze_panes == "B6"
    assert sheet.auto_filter.ref.startswith("A5:")
    assert sheet["A7"].value == "000123"  # identifiant texte, zéros conservés
    assert "NEXTGEN" in sheet.oddFooter.center.text


def test_pdf_a4_repeats_key_across_panels():
    blob = export_pdf(_rows(), FIELDS, title="Mouvements de stock",
                      warning="non émis")
    assert blob.startswith(b"%PDF")
    assert len(blob) > 2000


def test_format_dispatch_and_file_names():
    for fmt, mime in (
        ("csv", "text/csv"),
        ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("pdf", "application/pdf"),
    ):
        data, actual, extension = build_export(
            _rows(), FIELDS, fmt=fmt, title="Mouvements MP",
        )
        assert data and actual == mime and extension == fmt
        assert export_filename("Stock MP / 2026", fmt).startswith("NEXTGEN_")


def test_oversize_and_malformed_are_rejected_without_truncation():
    for bad_rows in ([{"reference": "x" * 10001}], [{"reference": "=1"}] * 251):
        with pytest.raises(ExportError):
            export_pdf(bad_rows, ["reference"], title="Test", warning="audit")
    with pytest.raises(ExportError):
        export_csv([{"reference": "x" * 10001}], ["reference"])
    with pytest.raises(ExportError):
        build_export(_rows(), FIELDS, fmt="html", title="Mouvements")
    with pytest.raises(ExportError):
        export_csv(_rows(), ["reference", "reference"])


def test_export_catalogue_whitelist_excludes_secrets_and_payroll():
    tables = {spec.table for spec in REPORTS.values()}
    assert len(REPORTS) >= 40
    assert not tables.intersection({
        "users", "permissions", "fiches_de_paie", "audit_trail", "logs",
        "erreurs", "ecritures_comptables", "erp_sku_fiscalite",
    })
    assert all("hash_mdp" not in spec.columns for spec in REPORTS.values())
    assert all("numero_compte" not in spec.columns for spec in REPORTS.values())
    assert all("email_contact" not in spec.columns for spec in REPORTS.values())
    assert all("contact" not in spec.columns for spec in REPORTS.values())


def test_catalogue_reads_strict_scope_and_strips_unapproved_columns():
    calls = []
    def reader(table, **kwargs):
        calls.append((table, kwargs))
        assert table == "stock_actuel"
        assert kwargs == {"page_size": 500, "max_rows": 10000}
        return [{"mp_id": "MP-01", "quantite_disponible": 3,
                 "cmp_actuel": 12, "derniere_maj": "2026-11-20",
                 "extra_secret": "do-not-export"}]
    spec, rows = read_report("stock_mp", reader=reader)
    assert len(calls) == 1 and spec.table == "stock_actuel"
    assert rows == [{"mp_id": "MP-01", "quantite_disponible": 3,
                     "cmp_actuel": 12, "derniere_maj": "2026-11-20"}]


def test_catalogue_denies_unknown_or_unreadable_table_and_invalid_period():
    def forbidden(*args, **kwargs):
        raise PermissionError("Accès refusé")
    with pytest.raises(PermissionError):
        read_report("stock_mp", reader=forbidden)
    with pytest.raises(ValueError):
        read_report("users", reader=forbidden)
    with pytest.raises(ValueError):
        read_report("stock_mp", start_date="2026-11-01",
                    end_date="2026-11-20", reader=forbidden)
    with pytest.raises(ValueError):
        read_report("mouvements_mp", start_date="2026-11-21",
                    end_date="2026-11-20", reader=forbidden)


def test_catalogue_rejects_incomplete_projection():
    def incomplete(table, **kwargs):
        return [{"mp_id": "MP-1"}]
    with pytest.raises(ValueError, match="Projection ERP incomplète"):
        read_report("stock_mp", reader=incomplete)
