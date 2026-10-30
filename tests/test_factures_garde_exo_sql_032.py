"""Migration 032 : garde transactionnelle conservative, sans activer TVA 0 %.

Les tests unitaires verifient le contrat source uniquement. L'installation
sur production doit ensuite etre verifiee dans pg_trigger/pg_proc et
par consultation des donnees existantes, SANS facture fictive.
"""
from pathlib import Path

SQL = (
    Path(__file__).resolve().parents[1]
    / "sql" / "032_factures_garde_exonerations_historique.sql"
).read_text(encoding="utf-8")


def test_guard_032_couvre_insertion_et_validation_directes():
    assert "CREATE TRIGGER erp_factures_garde_exonerations" in SQL
    assert "BEFORE INSERT OR UPDATE ON public.factures" in SQL
    assert "IF TG_OP = 'INSERT' THEN" in SQL
    assert "NEW.statut IN ('BROUILLON','VALIDE')" in SQL
    assert "NEW.statut IS DISTINCT FROM OLD.statut" in SQL
    assert "NEW.montant_tva IS DISTINCT FROM OLD.montant_tva" in SQL
    assert "NEW.taux_tva IS DISTINCT FROM OLD.taux_tva" in SQL
    assert "NEW.client_id IS DISTINCT FROM OLD.client_id" in SQL
    assert "NEW.remise_globale IS DISTINCT FROM OLD.remise_globale" in SQL


def test_guard_032_refuse_tous_les_dossiers_sans_modifier_le_taux():
    assert "FROM public.erp_exonerations_tva_clients d" in SQL
    assert "d.client_id = NEW.client_id" in SQL
    guard = SQL.split("CREATE FUNCTION erp_private.erp_factures_verrou_exonerations()", 1)[1]
    guard = guard.split("$fn$;", 1)[0]
    assert "d.statut" not in guard
    for forbidden in ("0.09", "0.19", "UPDATE public.factures", "INSERT INTO public.factures"):
        assert forbidden not in guard
    assert "RETURN NEW;" in guard


def test_guard_032_serialise_creation_attestation_et_facture():
    assert "CREATE OR REPLACE FUNCTION erp_private.erp_exo_garder_entete()" in SQL
    assert SQL.count("pg_catalog.hashtextextended(NEW.client_id, 25026)") >= 2
    assert "pg_catalog.pg_advisory_xact_lock" in SQL
    assert "IF TG_OP = 'INSERT' THEN" in SQL


def test_guard_032_preserve_les_droits_et_ne_peuple_pas_production():
    assert "SECURITY INVOKER" in SQL
    assert "SET search_path = pg_catalog" in SQL
    assert "REVOKE ALL ON FUNCTION erp_private.erp_factures_verrou_exonerations()" in SQL
    assert "FROM PUBLIC, anon, authenticated, service_role;" in SQL
    assert "CREATE POLICY" not in SQL
    assert "GRANT EXECUTE" not in SQL
    assert "INSERT INTO public.erp_exonerations_tva_clients" not in SQL
    assert "INSERT INTO public.factures" not in SQL
    assert "erp_sale_transaction" not in SQL
    assert SQL.strip().startswith("-- ERP 032")
    assert SQL.rstrip().endswith("COMMIT;")


def test_sql_032_parser_postgres_si_disponible():
    import pytest
    pglast = pytest.importorskip("pglast")
    pglast.parse_sql(SQL)
