"""Contrat SQL du diagnostic TVA/SKU, en lecture seule, sans données fabriquées."""
from pathlib import Path

import pytest

pglast = pytest.importorskip("pglast")
SQL = (Path(__file__).resolve().parents[1] /
       "sql/047_audit_preparation_tva_sku_lecture_seule.sql").read_text(encoding="utf-8")


def test_sql_047_postgresql_parse():
    parsed = pglast.parse_sql(SQL)
    assert len(parsed) == 4
    assert pglast.parse_plpgsql(
        SQL[SQL.index("CREATE OR REPLACE FUNCTION"):SQL.index("REVOKE ALL ON FUNCTION")]
    )


def test_sql_047_certifie_uniquement_preparation_technique():
    for expected in (
        "LANGUAGE plpgsql STABLE SECURITY INVOKER",
        "SANS_FICHE", "CONFLIT_VERSIONS", "HORS_MOTEUR_PILOTE",
        "A_VALIDER", "TAUX_A_VERIFIER", "PRET_TECHNIQUEMENT",
        "q.statut = 'VALIDEE'", "p.statut_juridique='en_vigueur'",
        "p.niveau_confiance='CONFIRMEE'", "f.nb > 1",
        "r.nb <> 1 OR r.valide <> 1",
        "WHERE s.actif='OUI'",
        "REVOKE ALL ON FUNCTION public.erp_tva_sku_readiness(date)",
        "FROM PUBLIC, anon, authenticated;",
        "TO service_role;",
    ):
        assert expected in SQL
    for unwanted in ("INSERT INTO", "UPDATE public.", "DELETE FROM",
                     "DROP TABLE", "TRUNCATE", "SECURITY DEFINER"):
        assert unwanted not in SQL.upper()
