"""Règles référentielles CNAS, sans taux actifs pour la paie."""
from pathlib import Path
import pytest

SQL = (Path(__file__).resolve().parents[1] / "sql" /
       "024_references_cnas_generales_2026.sql").read_text(encoding="utf-8")


def test_sql_cnas_syntaxe_postgresql():
    parser=pytest.importorskip("pglast")
    assert len(parser.parse_sql(SQL))>=3


def test_parts_officielles_regime_general():
    assert "'CNAS_REG_GENERAL_EMPLOYEUR_REF','CNAS',0.25::numeric" in SQL
    assert "'CNAS_REG_GENERAL_SALARIE_REF','CNAS',0.09::numeric" in SQL
    assert "'CNAS_REG_GENERAL_FONDS_OEUVRES_REF','CNAS',0.005::numeric" in SQL
    assert "0.345::numeric" in SQL
    assert "https://www.joradp.dz/FTP/jo-francais/2015/F2015049.pdf" in SQL


def test_taux_reference_non_executables():
    assert SQL.count("'a_confirmer','RECOUPEE'") == 3
    assert "'CNAS_SALARIE_TAUX'," not in SQL
    assert "'CNAS_EMPLOYEUR_TAUX'," not in SQL
    assert "INSERT INTO public.scf_pieces" not in SQL
    assert "INSERT INTO public.factures" not in SQL
    assert "INSERT INTO public.parametres_reglementaires" in SQL
    assert "ON CONFLICT (code,date_effet) DO NOTHING" in SQL
    assert "DO UPDATE" not in SQL


def test_pas_de_droits_ni_donnees_personnelles():
    for forbidden in (
        "DROP TABLE", "TRUNCATE", "DELETE FROM", "GRANT ",
        "DISABLE ROW LEVEL SECURITY", "INSERT INTO public.employes",
        "UPDATE public.parametres_reglementaires",
        "INSERT INTO public.scf_exercices",
    ):
        assert forbidden not in SQL
    assert SQL.startswith("-- ERP 024")
    assert SQL.rstrip().endswith("COMMIT;")
