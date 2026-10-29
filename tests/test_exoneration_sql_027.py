"""Contrats de sécurité de la migration 027, sans accès BDD."""
from pathlib import Path

SQL = (Path(__file__).resolve().parents[1] / "sql" /
       "027_circuit_admin_exonerations.sql").read_text(encoding="utf-8")


def test_027_double_validation_et_aucune_attribution_implicite():
    assert "CREATE TABLE public.erp_exonerations_tva_validateurs" in SQL
    assert "actif boolean NOT NULL DEFAULT false" in SQL
    assert "validateur fiscal" in SQL.lower()
    assert "d.cree_par=p_actor_id" in SQL
    assert "verification_documentaire" in SQL
    assert "reference_avis_validation" in SQL
    assert "A_VALIDER" in SQL
    assert "ERP_SALE_TRANSACTION" not in SQL.upper()


def test_027_acces_sql_limites_et_risques_d_autorisation():
    assert "SECURITY DEFINER" in SQL
    assert "SET search_path = pg_catalog, pg_temp" in SQL
    assert "erp_security_authorities" in SQL
    assert "habilita" not in SQL.lower() or "SECURITY_MANAGER" in SQL
    assert "REVOKE ALL ON FUNCTION public.erp_exoneration_tva_action" in SQL
    assert "TO service_role;" in SQL
    assert "has_function_privilege('authenticated'" in SQL
    assert "REVOKE ALL ON public.erp_exonerations_tva_validateurs" in SQL
    assert "REVOKE ALL ON public.erp_exonerations_tva_operations" not in SQL or "service_role" in SQL
    assert "CREATE POLICY" not in SQL


def test_027_idempotence_et_absence_seeds():
    assert "ON CONFLICT (operation_id) DO NOTHING" in SQL
    assert "FOR UPDATE" in SQL
    assert "op.payload<>p_payload" in SQL
    assert "INSERT INTO public.erp_exonerations_tva_operations" in SQL
    assert "INSERT INTO public.erp_exonerations_tva_validateurs" not in SQL
    assert "ALTER TABLE public.factures" not in SQL.lower()
    assert SQL.strip().endswith("COMMIT;")
