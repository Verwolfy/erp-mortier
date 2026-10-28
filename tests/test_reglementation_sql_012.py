"""Vérifications statiques du script, PAS un test d'exécution PostgreSQL."""
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / "sql" /
          "012_reglementation_registre.sql")
SQL = SOURCE.read_text(encoding="utf-8").lower()


def test_tables_reglementaires_et_journal_migrations():
    for table in ("schema_migrations", "parametres_reglementaires", "regles_reglementaires"):
        assert f"create table if not exists public.{table}" in SQL


def test_rls_active_sur_chaque_nouvelle_table():
    for table in ("schema_migrations", "parametres_reglementaires", "regles_reglementaires"):
        assert f"alter table public.{table} enable row level security" in SQL
        assert f"revoke all on public.{table} from public, anon, authenticated" in SQL


def test_pas_de_seed_ou_destructeur_dans_ce_lot():
    for token in ("insert into ", "delete from ", "truncate ", "drop table ", "grant all "):
        assert token not in SQL


def test_statuts_et_dates_reglementaires():
    for token in ("date_effet date not null", "date_verification date", "niveau_confiance",
                  "statut_juridique", "source text", "jsonb_typeof(donnees)"):
        assert token in SQL


def test_transaction_encadrante():
    assert SQL.lstrip().startswith("-- migration 012")
    assert SQL.rstrip().endswith("commit;")
    assert "begin;" in SQL
