"""Contrat du passage TAX-V2 au référentiel SKU existant, sans réseau."""
from pathlib import Path

import pytest

pglast = pytest.importorskip("pglast")
SQL = (Path(__file__).resolve().parents[1]
       / "sql/045_tva_preview_reconciliation_registre_sku.sql"
       ).read_text(encoding="utf-8")


def test_045_sql_analyse_postgresql_et_plpgsql():
    assert pglast.parse_sql(SQL)
    functions = []
    for stmt in pglast.split(SQL):
        pos = stmt.upper().find("CREATE OR REPLACE FUNCTION")
        if pos >= 0:
            functions.append(stmt[pos:])
    assert len(functions) == 1
    assert pglast.parse_plpgsql(functions[0])


def test_045_une_seule_source_tva_sku():
    assert "FROM public.erp_sku_fiscalite\n          WHERE sku_id = v_sku" in SQL
    assert "FROM public.erp_sku_tva_qualifications\n          WHERE sku_id = v_sku" not in SQL
    assert "statut = 'VALIDEE'" in SQL
    assert "statut = 'confirmee'" not in SQL
    assert "categorie_tva = 'NORMAL'" in SQL
    assert "categorie_tva = 'REDUIT'" in SQL
    assert "nullif(btrim(source_juridique), '') IS NOT NULL" in SQL
    assert "nullif(btrim(justification), '') IS NOT NULL" in SQL
    assert "date_verification IS NOT NULL" in SQL
    assert "date_validation IS NOT NULL" in SQL
    assert "v_qual_count <> 1 OR v_qual_invalid <> 0" in SQL
    assert "v_rate_count <> 1 OR v_rate_invalid <> 0" in SQL


def test_045_garde_et_neutralisation_table_pilote():
    assert "IF EXISTS (SELECT 1 FROM public.erp_sku_tva_qualifications)" in SQL
    assert "REVOKE ALL ON TABLE public.erp_sku_tva_qualifications FROM service_role;" in SQL
    assert "REVOKE ALL ON SEQUENCE public.erp_sku_tva_qualifications_qualification_id_seq" in SQL
    assert "COMMENT ON TABLE public.erp_sku_tva_qualifications" in SQL
    assert "CREATE OR REPLACE FUNCTION public.erp_sale_transaction" not in SQL
    assert "INSERT INTO public.erp_sku_fiscalite" not in SQL
    assert "DELETE FROM public.erp_sku_fiscalite" not in SQL
    assert "UPDATE public.erp_sku_fiscalite" not in SQL
    assert "DROP TABLE" not in SQL
    assert "SECURITY INVOKER" in SQL
