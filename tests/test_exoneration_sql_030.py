"""Contrat de journal d'audit métier 030 : identité, source et droits.

Exécution SQL véritable vérifiée séparément sur Supabase TEST sous ROLLBACK.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / "sql" / "030_journal_acteur_metier_exoneration.sql").read_text(
    encoding="utf-8"
)
SMOKE = (ROOT / "sql" / "030_smoke_test_rollback.sql").read_text(
    encoding="utf-8"
)


def test_journal_capture_acteur_metier_et_uuid_operation():
    assert "ADD COLUMN acteur_metier text REFERENCES public.users(user_id)" in SQL
    assert "ADD COLUMN operation_id uuid REFERENCES public.erp_exonerations_tva_operations(operation_id)" in SQL
    assert "CREATE OR REPLACE FUNCTION erp_private.erp_exo_journaliser_entete()" in SQL
    assert "CREATE OR REPLACE FUNCTION public.erp_exoneration_tva_action" in SQL
    assert "set_config('erp.exo_actor_id',p_actor_id,true)" in SQL
    assert "set_config('erp.exo_operation_id',p_operation_id::text,true)" in SQL
    assert "current_setting('erp.exo_actor_id',true)" in SQL
    assert "current_setting('erp.exo_operation_id',true)" in SQL


def test_journal_continue_a_refuser_les_roles_navigateur():
    assert "SECURITY DEFINER" in SQL
    assert "SET search_path = pg_catalog, pg_temp" in SQL
    assert "REVOKE ALL ON FUNCTION public.erp_exoneration_tva_action" in SQL
    assert "TO service_role;" in SQL
    assert "has_table_privilege('authenticated'" in SQL
    assert "REVOKE ALL ON FUNCTION erp_private.erp_exo_journaliser_entete()" in SQL
    assert "CREATE POLICY" not in SQL
    assert "GRANT INSERT" not in SQL
    assert SQL.rstrip().endswith("COMMIT;")


def test_journal_n_attribue_aucun_droit_fiscal_et_smoke_rollback():
    assert "INSERT INTO public.erp_exonerations_tva_validateurs" not in SQL
    assert "INSERT INTO public.erp_sku_fiscalite" not in SQL
    assert "erp_sale_transaction" not in SQL
    assert "CREATE TABLE public.erp_exonerations_tva_clients" not in SQL
    assert "JOIN public.erp_exonerations_tva_operations o" in SMOKE
    assert "e.acteur_metier=o.acteur_id" in SMOKE
    assert "e.type_evenement=CASE o.action" in SMOKE
    assert SMOKE.rstrip().endswith("ROLLBACK;")
