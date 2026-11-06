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
    assert 'client.rpc("erp_cost_document_pool_atomic"' in srv
    assert '"p_scf_ligne_id": scf_line_id' in srv
    assert 'document_pool(period_id, pool_ref, scf_piece, int(scf_line), explanation)' in ui
    assert 'UUID de la pièce SCF validée' in ui


def test_quantitative_line_reconciliation_contract():
    sql = (ROOT / "sql" / "040_couts_industriels_plafond_ligne_scf.sql").read_text(encoding="utf-8")
    assert "scf_ligne_id bigint NOT NULL" in sql
    assert "UNIQUE(scf_ligne_id)" in sql
    assert "l.piece_id=NEW.piece_id" in sql
    assert "v_amount>v_debit" in sql
    assert "NEW.montant_dzd>v_debit" in sql
    assert "p.montant_dzd>l.debit" in sql
    assert "SECURITY DEFINER" in sql
    assert "erp_apply_stock_movement" not in sql
    srv = (ROOT / "modules" / "production" / "cost_service.py").read_text(encoding="utf-8")
    assert '"p_scf_ligne_id": scf_line_id' in srv
    assert 'Decimal(str(pools[0]["montant_dzd"])) > debit' in srv


def test_atomic_documentation_contract():
    sql = (ROOT / "sql" / "041_couts_industriels_documentation_atomique.sql").read_text(encoding="utf-8")
    assert "SECURITY DEFINER" in sql
    assert "FOR UPDATE" in sql
    assert "erp_cost_pool_scf_evidence" in sql
    assert "statut='DOCUMENTE'" in sql
    assert "p_scf_ligne_id" in sql
    assert "REVOKE ALL ON FUNCTION" in sql
    assert "GRANT EXECUTE ON FUNCTION" in sql
    assert "erp_apply_stock_movement" not in sql


def test_validation_snapshot_and_drift_contract():
    sql = (ROOT / "sql" / "042_snapshot_validation_couts_industriels.sql").read_text(encoding="utf-8")
    assert "erp_cost_of_validation_snapshot" in sql
    assert "AFTER UPDATE OF statut" in sql
    assert "OLD.statut='BROUILLON'" in sql
    assert "NEW.statut='VALIDE'" in sql
    assert "IS DISTINCT FROM" in sql
    assert "security_invoker=true" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "GRANT SELECT ON public.erp_cost_of_validation_snapshot TO service_role" in sql
    assert "GRANT SELECT ON public.erp_cost_of_validation_drift TO service_role" in sql
    assert "erp_apply_stock_movement" not in sql
    srv = (ROOT / "modules" / "production" / "cost_service.py").read_text(encoding="utf-8")
    ui = (ROOT / "modules" / "production" / "cost_views.py").read_text(encoding="utf-8")
    assert '"validation_drift": (' in srv
    assert '"erp_cost_of_validation_drift"' in srv
    assert 'client.table(table_name).select(columns)' in srv
    assert 'section == "validation_drift"' in ui
    assert 'report["validation_drift"]' in ui
    assert 'derive_detectee' in ui


def test_validated_snapshot_export_is_read_only_bounded_and_server_only():
    sql = (ROOT / "sql" / "043_export_couts_valides_snapshot.sql").read_text(encoding="utf-8")
    assert "STABLE SECURITY DEFINER" in sql
    assert "SET search_path=pg_catalog,public" in sql
    assert "v_period.statut IS DISTINCT FROM 'VALIDE'" in sql
    assert "v_pool_count>5000" in sql
    assert "v_of_count>5000" in sql
    assert "v_driver_count>10000" in sql
    assert "v_pool_count<>v_evidence_count" in sql
    assert "abs(v_pool_total-v_alloc_total)>=0.00001" in sql
    assert "single_sql_statement" in sql
    assert "erp_cost_of_validation_snapshot" in sql
    assert "REVOKE ALL ON FUNCTION public.erp_cost_export_validated(text)" in sql
    assert "GRANT EXECUTE ON FUNCTION public.erp_cost_export_validated(text)" in sql
    assert "erp_apply_stock_movement" not in sql


def test_validated_snapshot_export_fixture_rolls_back():
    fixture = (ROOT / "sql" / "test_isole" /
               "20261106_export_transactionnel_048_ROLLBACK.sql").read_text(encoding="utf-8")
    assert fixture.startswith("-- TEST UNIQUEMENT")
    assert fixture.rstrip().endswith("ROLLBACK;")
    assert "COST_EXPORT_SNAPSHOT_OK" in fixture
    assert "Export brouillon autorisé" in fixture
    assert "Instantané export modifié après dérive OF" in fixture
