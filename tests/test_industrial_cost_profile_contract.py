"""Contrat de sécurité du profilage analytique 047 en transaction isolée."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "sql" / "test_isole" / "20261106_profilage_audit_industriel_047_ROLLBACK.sql"


def test_profile_is_transactional_and_does_not_write_accounting():
    source = SQL.read_text(encoding="utf-8")
    assert "BEGIN;" in source
    assert source.rstrip().endswith("ROLLBACK;")
    assert "generate_series(1,500)" in source
    assert "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)" in source
    assert "erp_cost_period_audit" in source
    assert "COST_PROFILE_047_OK" in source
    assert "statement_timeout" in source
    assert "lock_timeout" in source
    assert "scf_pieces" not in source
    assert "erp_apply_stock_movement" not in source
    assert "stock_actuel_pf" not in source


def test_profile_guard_protects_against_existing_fixture_ids():
    source = SQL.read_text(encoding="utf-8")
    assert "Fixtures de profilage déjà présentes" in source
    assert "IT26_PROFILE_047" in source
    assert "IT26_PROFILE_OF_" in source
    assert "sum(montant_impute_dzd)" in source
