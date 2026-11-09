"""Contrat d'innocuité du candidat TAX-V2, sans connexion PostgreSQL.

La syntaxe valide ne prouve pas que la migration est déployable en production.
"""
from pathlib import Path

import pytest

pglast = pytest.importorskip("pglast")
SQL_PATH = (
    Path(__file__).resolve().parents[1]
    / "sql/supabase_pending/erp_tax_classification_preview_CANDIDAT_NON_EXECUTE.sql"
)
SQL = SQL_PATH.read_text(encoding="utf-8")


def test_candidate_sql_pg17_parser_and_function_body():
    assert pglast.parse_sql(SQL)
    functions = [
        stmt for stmt in pglast.split(SQL)
        if stmt.lstrip().upper().startswith("CREATE OR REPLACE FUNCTION")
    ]
    assert len(functions) == 2
    for function in functions:
        assert pglast.parse_plpgsql(function)


def test_candidate_readonly_calculation_and_strict_roles():
    assert "CREATE TABLE IF NOT EXISTS public.erp_sku_tva_qualifications" in SQL
    assert "ENABLE ROW LEVEL SECURITY" in SQL
    assert "GRANT SELECT, INSERT, UPDATE ON TABLE public.erp_sku_tva_qualifications TO service_role" in SQL
    assert "REVOKE ALL ON TABLE public.erp_sku_tva_qualifications FROM PUBLIC, anon, authenticated" in SQL
    assert "SECURITY INVOKER" in SQL
    assert "LANGUAGE plpgsql STABLE" in SQL
    assert "REVOKE ALL ON FUNCTION public.erp_tax_preview_classified(jsonb,date,boolean)" in SQL
    assert "FROM PUBLIC, anon, authenticated;" in SQL
    assert "TO service_role;" in SQL
    assert "SET search_path = pg_catalog, public" in SQL
    assert "CREATE OR REPLACE FUNCTION public.erp_sale_transaction" not in SQL
    assert "INSERT INTO public.factures" not in SQL
    assert "UPDATE public.factures" not in SQL
    assert "INSERT INTO public.lignes_facture" not in SQL


def test_candidate_failclosed_for_sku_provenance_tva_and_cash():
    for guard in (
        "p_cash IS DISTINCT FROM false",
        "v_qual_count <> 1",
        "v_qual_invalid <> 0",
        "statut = 'confirmee'",
        "v_rate_count <> 1",
        "v_rate_invalid <> 0",
        "niveau_confiance = 'CONFIRMEE'",
        "unite = 'fraction'",
        "valeur BETWEEN 0 AND 1",
        "date_effet <= p_date",
        "date_fin IS NULL OR date_fin >= p_date",
        "nullif(btrim(valide_par), '') IS NOT NULL",
        "v_sku = ANY(v_seen)",
        "CALCUL_ISOLE_NON_COMPTABILISE",
    ):
        assert guard in SQL


def test_candidate_decimal_expects_canonical_string():
    assert "jsonb_typeof(v_line->'montant_ht') <> 'string'" in SQL
    assert "(\\.[0-9]{1,2})?" in SQL
    assert "(\\\\.[0-9]{1,2})?" not in SQL
    assert "v_amount >= 1000000000000000" in SQL
    assert "round(v_amount * v_rate, 2)" in SQL


def test_candidate_non_executed_filename_and_transaction():
    assert "NON_EXECUTE" in SQL_PATH.name
    assert SQL.lstrip().startswith("-- CANDIDAT NON EXÉCUTÉ")
    assert "BEGIN;" in SQL
    assert SQL.rstrip().endswith("COMMIT;")


def test_candidate_qualifications_are_auditable_and_immutable():
    assert "BEFORE UPDATE OR DELETE ON public.erp_sku_tva_qualifications" in SQL
    assert "OLD.statut IN ('confirmee', 'rejetee')" in SQL
    assert "IF TG_OP = 'DELETE'" in SQL
    assert "EXECUTE FUNCTION public.erp_sku_tva_historique_immuable()" in SQL
    assert "REVOKE ALL ON FUNCTION public.erp_sku_tva_historique_immuable()" in SQL


def test_candidate_refuses_inactive_sku_and_client_tax_self_classification():
    assert "WHERE sku_id = v_sku AND actif = 'OUI'" in SQL
    assert "FROM public.erp_sku_tva_qualifications" in SQL
    assert "v_line->>'code_tva'" not in SQL
    assert "v_line->>'classification_verifiee'" not in SQL
