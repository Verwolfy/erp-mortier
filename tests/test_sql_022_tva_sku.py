"""Contrats SQL 022 : table TVA privée, aucun mouvement financier."""
from pathlib import Path
import pytest

SQL = (Path(__file__).resolve().parents[1] / "sql" /
       "022_qualification_tva_sku.sql").read_text(encoding="utf-8")


def test_analyse_sql():
    pglast = pytest.importorskip("pglast")
    assert len(pglast.parse_sql(SQL)) >= 5


def test_acces_serveur_seul_sans_ecriture_exposee():
    assert "ENABLE ROW LEVEL SECURITY" in SQL
    assert "REVOKE ALL ON public.erp_sku_fiscalite FROM PUBLIC, anon, authenticated" in SQL
    assert "GRANT SELECT ON public.erp_sku_fiscalite TO service_role" in SQL
    assert "GRANT INSERT" not in SQL
    assert "GRANT UPDATE" not in SQL


def test_pas_de_qualification_fictive_ou_de_mutation_facture():
    assert "INSERT INTO public.erp_sku_fiscalite" not in SQL
    assert "UPDATE public.factures" not in SQL
    assert "erp_sale_transaction" not in SQL
    assert "date_verification IS NOT NULL" in SQL
    assert "date_validation IS NOT NULL" in SQL
    assert "valide_par" in SQL
    assert "PRIMARY KEY (sku_id, date_effet)" in SQL


def test_transaction_et_cle_etrangere():
    assert SQL.lstrip().startswith("-- ERP 022")
    assert "REFERENCES public.sku_conditionnement(sku_id)" in SQL
    assert "BEGIN;" in SQL
    assert SQL.rstrip().endswith("COMMIT;")
