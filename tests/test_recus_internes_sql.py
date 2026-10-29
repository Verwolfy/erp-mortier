"""Migration 020 : contrats RLS, idempotence, immutabilité.

Test statique sans requête ni écriture Supabase.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / "sql" / "020_recus_internes.sql").read_text(encoding="utf-8")


def test_creation_privee_et_restriction():
    assert "CREATE TABLE public.erp_recus_internes" in SQL
    assert "ALTER TABLE public.erp_recus_internes ENABLE ROW LEVEL SECURITY" in SQL
    assert "REVOKE ALL ON public.erp_recus_internes FROM PUBLIC, anon, authenticated" in SQL
    assert "GRANT SELECT, INSERT ON public.erp_recus_internes TO service_role" in SQL
    assert "SECURITY INVOKER" in SQL
    assert "GRANT EXECUTE ON FUNCTION public.erp_emettre_recu_interne(text,text) TO service_role" in SQL


def test_rattachement_et_antidoublon():
    for expression in (
        "reglement_id text NOT NULL UNIQUE",
        "operation_id text NOT NULL UNIQUE",
        "REFERENCES public.reglements(reglement_id)",
        "FOR UPDATE",
        "v_recu.operation_id IS DISTINCT FROM p_operation_id",
        "v_recu.montant_encaisse IS DISTINCT FROM v_reg.montant_total",
    ):
        assert expression in SQL


def test_donnees_fiscales_non_liquidees_et_immuables():
    for expression in (
        "INTERNE_NON_FISCAL",
        "NON_CALCULE",
        "CREATE TRIGGER erp_recus_internes_immutables",
        "BEFORE UPDATE OR DELETE",
        "Recu interne immuable",
    ):
        assert expression in SQL
    assert "UPDATE public.factures" not in SQL
    assert "INSERT INTO public.factures" not in SQL
    assert "UPDATE public.reglements" not in SQL


def test_sql_parsable():
    pg = pytest.importorskip("pglast")
    statements = pg.parse_sql(SQL)
    assert len(statements) >= 8
    assert SQL.rstrip().endswith("COMMIT;")
    assert pg.parse_plpgsql(next(
        item for item in pg.split(SQL)
        if item.startswith("CREATE FUNCTION public.erp_emettre_recu_interne")
    ))
