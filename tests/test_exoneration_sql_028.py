"""Contrats statiques : lecture de l'autorisation fiscale 028."""
from pathlib import Path

SQL = (Path(__file__).resolve().parents[1] / "sql" /
       "028_statut_habilitation_fiscale.sql").read_text(encoding="utf-8")


def test_habilitation_fiscale_distincte_en_sql():
    assert "erp_exoneration_tva_is_validator(p_actor_id text)" in SQL
    assert "erp_exonerations_tva_validateurs" in SQL
    assert "erp_security_authorities" in SQL
    assert "a.habilitation='SECURITY_MANAGER'" in SQL
    assert "v.actif IS TRUE" in SQL
    assert "a.retire_le IS NULL" in SQL


def test_habilitation_fiscale_non_exposee_aux_clients():
    assert "SECURITY DEFINER" in SQL
    assert "SET search_path = pg_catalog, pg_temp" in SQL
    assert "REVOKE ALL PRIVILEGES ON FUNCTION" in SQL
    assert "FROM PUBLIC,anon,authenticated,service_role;" in SQL
    assert "TO service_role;" in SQL
    assert "GRANT EXECUTE" in SQL
    assert "GRANT INSERT" not in SQL
    assert "CREATE POLICY" not in SQL
    assert "INSERT INTO public.erp_exonerations_tva_validateurs" not in SQL
    assert SQL.rstrip().endswith("COMMIT;")
