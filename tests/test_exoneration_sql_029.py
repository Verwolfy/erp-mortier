"""Régression SQL 029 : refuser l'homologation d'attestations obsolètes.

Ce test ne remplace pas l'essai transactionnel TEST sous ROLLBACK.
"""
from pathlib import Path

SQL = (Path(__file__).resolve().parents[1] / "sql" /
       "029_recontrole_client_skus_validation.sql").read_text(encoding="utf-8")


def test_recontrole_client_et_tous_les_skus_a_la_validation():
    assert "CREATE OR REPLACE FUNCTION public.erp_exoneration_tva_action" in SQL
    assert "ELSIF p_action='VALIDER' THEN" in SQL
    assert "client devenu inactif" in SQL
    assert "portée SKU vide ou inactive" in SQL
    assert "FROM public.clients c" in SQL
    assert "LEFT JOIN public.sku_conditionnement s" in SQL
    assert "WHERE p.attestation_id=d.attestation_id" in SQL
    assert "s.sku_id IS NULL" in SQL
    assert "UPPER" in SQL.upper()
    assert "('OUI','TRUE','YES','1')" in SQL


def test_recontrole_preserve_securite_et_idempotence():
    assert "SECURITY DEFINER" in SQL
    assert "SET search_path = pg_catalog, pg_temp" in SQL
    assert "ON CONFLICT (operation_id) DO NOTHING" in SQL
    assert "FOR UPDATE" in SQL
    assert "erp_exonerations_tva_validateurs" in SQL
    assert "d.cree_par=p_actor_id" in SQL
    assert "REVOKE ALL ON FUNCTION" in SQL
    assert "TO service_role;" in SQL
    assert "has_function_privilege('authenticated'" in SQL
    assert SQL.rstrip().endswith("COMMIT;")


def test_029_n_affecte_ni_facturation_ni_valideurs_existants():
    assert "erp_sale_transaction" not in SQL
    assert "INSERT INTO public.erp_exonerations_tva_validateurs" not in SQL
    assert "GRANT EXECUTE" in SQL
    assert "DROP FUNCTION" not in SQL
    assert "DROP TABLE" not in SQL
    assert "TRUNCATE" not in SQL
