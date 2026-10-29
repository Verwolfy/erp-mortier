"""Contrat de sécurité de la migration 025 (complément des tests TEST/PROD).

Test statique sans accès Supabase : une CI verte ne remplace PAS la
vérification des ACL réelles, des FKs et de RLS dans chaque projet.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / "sql" / "025_attestations_exoneration_client.sql").read_text(
    encoding="utf-8"
)


def test_migration_attestations_schema_et_portees():
    assert SQL.lstrip().startswith("-- ERP 025")
    assert "CREATE TABLE public.erp_exonerations_tva_clients" in SQL
    assert "CREATE TABLE public.erp_exonerations_tva_skus" in SQL
    assert "REFERENCES public.clients(client_id)" in SQL
    assert "REFERENCES public.sku_conditionnement(sku_id)" in SQL
    assert "PRIMARY KEY (attestation_id, sku_id)" in SQL
    assert "UNIQUE (client_id, reference_attestation)" in SQL
    assert SQL.rstrip().endswith("COMMIT;")


def test_tables_privees_et_roles_limités():
    assert "ALTER TABLE public.erp_exonerations_tva_clients ENABLE ROW LEVEL SECURITY" in SQL
    assert "ALTER TABLE public.erp_exonerations_tva_skus ENABLE ROW LEVEL SECURITY" in SQL
    assert re.search(r"REVOKE ALL PRIVILEGES.+FROM PUBLIC, anon, authenticated, service_role", SQL, re.S)
    assert re.search(
        r"GRANT SELECT ON TABLE public\.erp_exonerations_tva_clients,\s*"
        r"public\.erp_exonerations_tva_skus TO service_role", SQL
    )
    assert "CREATE POLICY" not in SQL
    assert "GRANT INSERT" not in SQL
    assert "GRANT UPDATE" not in SQL
    assert "GRANT DELETE" not in SQL


def test_absence_seeds_et_modifications_de_factures():
    executable = "\n".join(
        ligne for ligne in SQL.splitlines() if not ligne.lstrip().startswith("--")
    ).upper()
    assert "INSERT INTO" not in executable
    assert "UPDATE PUBLIC." not in executable
    assert "ERP_SALE_TRANSACTION" not in executable
    assert "ALTER TABLE PUBLIC.FACTURES" not in executable
    assert "DROP TABLE" not in executable
