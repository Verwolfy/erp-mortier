"""Migration 023 : aucune écriture directe de la clé serveur."""
from pathlib import Path
import pytest
SQL=(Path(__file__).resolve().parents[1]/"sql"/"023_tva_sku_acl_lecture.sql").read_text(encoding="utf-8")

def test_acl_023_parsable():
    pglast=pytest.importorskip("pglast")
    assert len(pglast.parse_sql(SQL)) >= 4

def test_acl_023_moindre_privilege():
    assert "REVOKE ALL PRIVILEGES ON TABLE public.erp_sku_fiscalite FROM service_role" in SQL
    assert "GRANT SELECT ON TABLE public.erp_sku_fiscalite TO service_role" in SQL
    assert "has_table_privilege('service_role','public.erp_sku_fiscalite','INSERT')" in SQL
    assert "has_table_privilege('anon','public.erp_sku_fiscalite','SELECT')" in SQL
    assert SQL.rstrip().endswith("COMMIT;")
