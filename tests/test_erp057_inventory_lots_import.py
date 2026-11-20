"""ERP-057 : lots et import XLSX sous protections métier, sans Supabase réel."""
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from openpyxl import Workbook, load_workbook

from modules.stocks.inventory_excel import (
    InventoryImportError, _number, export_count_template, parse_count_workbook,
)
from modules.stocks import inventory_service as service


SNAPSHOT = [
    {"type_article": "MP", "article_id": "MP-001", "quantite_theorique": "10"},
    {"type_article": "PF", "article_id": "SKU-0005", "quantite_theorique": "0"},
]


def _workbook(snapshot=SNAPSHOT):
    wb = load_workbook(BytesIO(export_count_template(snapshot)))
    ws = wb.active
    return wb, ws


def _bytes(wb):
    out = BytesIO()
    wb.save(out)
    wb.close()
    return out.getvalue()


def test_template_is_blank_with_nextgen_identity_and_reference_ids():
    wb, ws = _workbook()
    assert "NEXTGEN" in ws["A1"].value
    assert [ws.cell(5, i).value for i in range(1, 5)] == [
        "type_article", "article_id", "quantite_comptee", "motif_ecart"]
    assert ws["B7"].value == "SKU-0005"
    assert ws["C6"].value is None and ws["C7"].value is None
    assert ws["B7"].number_format == "@"
    wb.close()


def test_import_partial_counts_and_keeps_zero_as_real_count():
    wb, ws = _workbook()
    ws["C6"] = "9.125"
    ws["D6"] = "Perte observée et documentée"
    ws["C7"] = 0
    rows = parse_count_workbook(_bytes(wb), SNAPSHOT)
    assert rows == [
        {"type_article": "MP", "article_id": "MP-001",
         "quantite_comptee": "9.125", "motif_ecart": "Perte observée et documentée"},
        {"type_article": "PF", "article_id": "SKU-0005",
         "quantite_comptee": "0", "motif_ecart": ""},
    ]


@pytest.mark.parametrize("value", ["-1", "NaN", "1e5", "1,50", "Infinity",
                                   True, None, "1000000000000000"])
def test_numbers_rejected_without_implicit_conversion(value):
    with pytest.raises(InventoryImportError):
        _number(value)


def test_formula_cells_rejected_without_evaluation():
    wb, ws = _workbook()
    ws["C6"] = "=1+2"
    with pytest.raises(InventoryImportError, match="Formules"):
        parse_count_workbook(_bytes(wb), SNAPSHOT)


def test_unknown_article_or_duplicate_fails_all():
    wb, ws = _workbook()
    ws["B6"] = "MP-INCONNUE"
    ws["C6"] = "10"
    with pytest.raises(InventoryImportError, match="absent"):
        parse_count_workbook(_bytes(wb), SNAPSHOT)
    wb, ws = _workbook()
    ws["C6"] = "10"
    ws["A8"] = "MP"
    ws["B8"] = "MP-001"
    ws["C8"] = "10"
    with pytest.raises(InventoryImportError, match="double"):
        parse_count_workbook(_bytes(wb), SNAPSHOT)


def test_missing_motive_or_unfilled_lines_fail_closed():
    wb, ws = _workbook()
    ws["C6"] = "9"
    with pytest.raises(InventoryImportError, match="justification"):
        parse_count_workbook(_bytes(wb), SNAPSHOT)
    with pytest.raises(InventoryImportError, match="Aucune quantité"):
        parse_count_workbook(export_count_template(SNAPSHOT), SNAPSHOT)


def test_numeric_article_id_must_remain_text():
    wb, ws = _workbook()
    ws["B6"] = 123
    ws["C6"] = 10
    with pytest.raises(InventoryImportError, match="Référence"):
        parse_count_workbook(_bytes(wb), SNAPSHOT)


def test_workbook_with_two_sheets_is_refused():
    wb, ws = _workbook()
    wb.create_sheet("Injection")
    with pytest.raises(InventoryImportError, match="Un seul onglet"):
        parse_count_workbook(_bytes(wb), SNAPSHOT)


def test_oversize_bytes_fail_before_openpyxl_parse():
    with pytest.raises(InventoryImportError, match="2 Mo"):
        parse_count_workbook(b"Z" * 2_000_001, SNAPSHOT)


def test_import_is_idempotent_for_same_actor_campaign_and_payload(monkeypatch):
    monkeypatch.setattr(service, "_identity", lambda **kw: ("USER-TEST", "MAGASINIER"))
    rpc = MagicMock(return_value={"inventaire_id": "INV-TEST-ABCDEFGH"})
    monkeypatch.setattr(service, "_rpc", rpc)
    rows = [{"type_article": "MP", "article_id": "MP-001",
             "quantite_comptee": "9", "motif_ecart": "Perte qualifiée"}]
    service.import_inventory_counts("INV-TEST-ABCDEFGH", rows)
    service.import_inventory_counts("INV-TEST-ABCDEFGH", rows)
    params1 = rpc.call_args_list[0].args[1]
    params2 = rpc.call_args_list[1].args[1]
    assert params1["p_operation_id"] == params2["p_operation_id"]
    assert params1["p_operation_id"].startswith("INVIMP-")
    assert len(params1["p_operation_id"]) < 110
    assert params1["p_rows"] == rows


def test_lot_reconciliation_flags_missing_register_without_adding_lots():
    summary = service.lot_reconciliation([
        {"type_article": "MP", "article_id": "DEMO26_MP2",
         "quantite_theorique": "220", "quantite_comptee": "220"},
        {"type_article": "PF", "article_id": "SKU-001",
         "quantite_theorique": "10", "quantite_comptee": "8"},
    ], [
        {"type_article": "PF", "article_id": "SKU-001", "lot_id": "LOT-A",
         "quantite_theorique": "10", "quantite_comptee": "7"},
    ])
    assert summary["articles_non_reconcilies"] == 2
    assert summary["lignes"][0]["ecart_tracabilite"] == "220"
    assert summary["lignes"][0]["anomalie"] == "A_RECONCILIER"
    assert summary["lignes"][1]["ecart_comptage_lots"] == "1"
    assert summary["lots_non_comptes"] == 0


def test_lot_count_uses_authorized_rpc_not_direct_stock_update(monkeypatch):
    monkeypatch.setattr(service, "_identity", lambda **kw: ("USER-TEST", "MAGASINIER"))
    rpc = MagicMock(return_value={"inventaire_id": "INV-TEST-ABCDEFGH"})
    monkeypatch.setattr(service, "_rpc", rpc)
    service.count_inventory_lot("INV-TEST-ABCDEFGH", "LOT-1", "0", "Perte justifiée")
    assert rpc.call_args.args[0] == "erp_inventory_count_lot"
    assert rpc.call_args.args[1]["p_quantite"] == "0"


def test_sql_never_mutates_live_stock_or_scf_and_denies_public_calls():
    base = Path(__file__).resolve().parents[1] / "sql"
    sql = (base / "ERP_057a_lots_import_atomique_20261120.sql").read_text()
    guard = (base / "ERP_057b_inventaire_gardes_lots_20261120.sql").read_text()
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "REVOKE ALL ON public.erp_inventaire_lots FROM PUBLIC,anon,authenticated" in sql
    assert "ON CONFLICT(operation_id) DO NOTHING" in sql
    assert "GET DIAGNOSTICS v_delta=ROW_COUNT" in sql
    assert "BEFORE UPDATE OF statut" in guard
    assert "quantite_comptee IS NULL" in guard
    assert "Lots non réconciliés" in guard
    for content in (sql, guard):
        assert "UPDATE public.stock_actuel " not in content
        assert "UPDATE public.stock_actuel_pf " not in content
        assert "INSERT INTO public.mouvements " not in content
        assert "INSERT INTO public.ecritures_comptables" not in content



def test_template_cannot_be_reused_for_a_different_inventory():
    wb, ws = _workbook()
    wb.close()
    original = export_count_template(SNAPSHOT, campaign_id="INV-CAMPAIGN-A")
    with pytest.raises(InventoryImportError, match="autre campagne"):
        parse_count_workbook(original, SNAPSHOT, campaign_id="INV-CAMPAIGN-B")


def test_extra_columns_are_not_silently_ignored():
    wb, ws = _workbook()
    ws["E5"] = "source_externe"
    ws["C6"] = 10
    with pytest.raises(InventoryImportError, match="supplémentaires"):
        parse_count_workbook(_bytes(wb), SNAPSHOT)


def test_classify_difference_checks_role_and_reason(monkeypatch):
    monkeypatch.setattr(service, "_identity", lambda **kw: ("USR-TEST", "MAGASINIER"))
    rpc = MagicMock(return_value={"inventaire_id": "INV-TEST-ABCDEFGH"})
    monkeypatch.setattr(service, "_rpc", rpc)
    with pytest.raises(ValueError):
        service.classify_inventory_difference(
            "INV-TEST-ABCDEFGH", "MP", "MP-001", "TVA", "texte de justification"
        )
    with pytest.raises(ValueError):
        service.classify_inventory_difference(
            "INV-TEST-ABCDEFGH", "MP", "MP-001", "PERTE", "trop court"
        )
    service.classify_inventory_difference(
        "INV-TEST-ABCDEFGH", "MP", "MP-001", "PERTE",
        "Détérioration vérifiée et documentée",
    )
    assert rpc.call_args.args[0] == "erp_inventory_classify_difference"
    assert rpc.call_args.args[1]["p_acteur_id"] == "USR-TEST"


def test_adjustment_proposal_never_authorizes_execution():
    from modules.stocks.inventory_adjustment import build_adjustment_preparation
    dossier = build_adjustment_preparation(
        {"inventaire_id": "INV-TEST", "statut": "ECARTS_A_QUALIFIER",
         "valide_par": "VALIDATEUR"},
        [{"type_article": "MP", "article_id": "MP-01",
          "quantite_theorique": "10", "quantite_comptee": "8",
          "pmp_snapshot": "20", "nature_ecart": "PERTE",
          "qualification_note": "Détérioration observée"}],
        [{"type_article": "MP", "article_id": "MP-01", "lot_id": "LOT-1",
          "quantite_theorique": "10", "quantite_comptee": "8"}],
    )
    assert dossier["executable"] is False
    assert dossier["mouvements_stock_appliques"] is False
    assert dossier["lignes"][0]["operation_envisagee"] == "SORTIE"
    assert dossier["lignes"][0]["valeur_indicative_dzd"] == "40"
    assert dossier["lignes"][0]["statut_projet"] == "NON_EXECUTABLE"


def test_adjustment_fails_closed_without_lot_trace_or_cost():
    from modules.stocks.inventory_adjustment import build_adjustment_preparation
    dossier = build_adjustment_preparation(
        {"inventaire_id": "INV-TEST", "statut": "OUVERT"},
        [{"type_article": "PF", "article_id": "DEMO26_SKU2",
          "quantite_theorique": "60", "quantite_comptee": "58",
          "pmp_snapshot": None, "nature_ecart": "NON_QUALIFIE"}],
        [],
    )
    assert dossier["executable"] is False
    assert any("lots non réconciliés" in reason for reason in dossier["blocages"])
    assert any("non qualifiée" in reason for reason in dossier["blocages"])
    assert any("PMP" in reason for reason in dossier["blocages"])


def test_sql_classification_resets_after_recount_and_never_moves_stock():
    sql = (Path(__file__).resolve().parents[1] /
           "sql/ERP_057c_qualification_ecarts_20261120.sql").read_text()
    assert "NEW.nature_ecart='NON_QUALIFIE'" in sql
    assert "p_nature='RETOUR_CLIENT' AND v_delta<0" in sql
    assert "v_inv.statut<>'OUVERT'" in sql
    assert "UPDATE public.stock_actuel " not in sql
    assert "INSERT INTO public.mouvements " not in sql
