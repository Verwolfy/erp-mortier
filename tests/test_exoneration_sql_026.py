"""Contrats statiques du cycle attestations SQL 026 (CI hors base)."""
from pathlib import Path
import re

SQL = (Path(__file__).resolve().parents[1] / "sql" /
       "026_cycle_validation_exoneration_client.sql").read_text(encoding="utf-8")


def test_cycle_controle_validation_portee_et_concurrence():
    assert "CREATE SCHEMA IF NOT EXISTS erp_private" in SQL
    assert "CREATE TABLE public.erp_exonerations_tva_evenements" in SQL
    assert "Seul un brouillon non validé" in SQL
    assert "Validation impossible sans portée SKU" in SQL
    assert "Attestation client validée concurrente" in SQL
    assert "Attestation validée immuable sauf révocation" in SQL
    assert "Attestation révoquée immuable" in SQL
    assert "Portée modifiable uniquement sur brouillon" in SQL
    assert "pg_advisory_xact_lock" in SQL
    assert "REFERENCES public.erp_exonerations_tva_clients" in SQL
    assert SQL.rstrip().endswith("COMMIT;")


def test_cycle_interdit_exposition_et_writes_api():
    assert "SECURITY INVOKER" in SQL
    assert "SECURITY DEFINER" not in SQL
    assert "SET search_path = pg_catalog" in SQL
    assert "ALTER TABLE public.erp_exonerations_tva_evenements ENABLE ROW LEVEL SECURITY" in SQL
    assert re.search(r"REVOKE ALL ON public.erp_exonerations_tva_evenements\s+"
                     r"FROM PUBLIC, anon, authenticated, service_role", SQL)
    assert "REVOKE ALL ON ALL FUNCTIONS IN SCHEMA erp_private" in SQL
    assert "CREATE POLICY" not in SQL
    assert "GRANT EXECUTE" not in SQL
    assert "GRANT INSERT" not in SQL
    assert "GRANT UPDATE" not in SQL
    assert "erp_sale_transaction" not in SQL.lower()


def test_cycle_sans_seed_juridique_ni_facturation():
    code = "\n".join(line for line in SQL.splitlines()
                      if not line.lstrip().startswith("--")).upper()
    assert "INSERT INTO PUBLIC.ERP_EXONERATIONS_TVA_CLIENTS" not in code
    assert "INSERT INTO PUBLIC.ERP_EXONERATIONS_TVA_SKUS" not in code
    assert "ALTER TABLE PUBLIC.FACTURES" not in code
    assert "DROP TABLE" not in code
    assert "GRANT ALL" not in code
