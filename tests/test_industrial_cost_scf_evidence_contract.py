"""Contrat documentaire du coût industriel : pièces SCF validées requises."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_migration_refuses_manual_documented_flag():
    sql = (ROOT / "sql" / "038_couts_industriels_pieces_scf_validees.sql").read_text(encoding="utf-8")
    assert "erp_cost_pool_scf_evidence" in sql
    assert "REFERENCES public.scf_pieces(piece_id)" in sql
    assert "s.statut='VALIDEE'" in sql
    assert "s.date_validation IS NOT NULL" in sql
    assert "CREATE TRIGGER erp_cost_require_evidence_trigger" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "REVOKE ALL ON public.erp_cost_pool_scf_evidence" in sql
    assert "SECURITY DEFINER" in sql
    assert "erp_cost_validate_period" in sql
    assert "erp_apply_stock_movement" not in sql


def test_ui_service_requires_verified_scf_uuid():
    srv = (ROOT / "modules" / "production" / "cost_service.py").read_text(encoding="utf-8")
    ui = (ROOT / "modules" / "production" / "cost_views.py").read_text(encoding="utf-8")
    assert 'client.table("scf_pieces")' in srv
    assert 'pieces[0]["statut"] != "VALIDEE"' in srv
    assert 'client.table("erp_cost_pool_scf_evidence").upsert(' in srv
    assert 'on_conflict="pool_id"' in srv
    assert 'document_pool(period_id, pool_ref, scf_piece, explanation)' in ui
    assert 'UUID de la pièce SCF validée' in ui
