"""Validation syntaxique SQL/PLpgSQL PG17, sans aucune connexion à une base.

La syntaxe n'est pas une preuve de disponibilité des tables, de correction des
droits RLS ou de conformité fiscale. L'exécution sur TEST reste distincte.
"""
from pathlib import Path

import pytest

pglast = pytest.importorskip("pglast")

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "012_reglementation_registre.sql",
    "013_facturation_parametree.sql",
    "014_scf_journal.sql",
    "015_paie_privee.sql",
]


@pytest.mark.parametrize("filename", FILES)
def test_analyse_syntaxique_postgresql(filename):
    sql = (ROOT / "sql" / filename).read_text(encoding="utf-8")
    statements = pglast.parse_sql(sql)
    assert len(statements) >= 4
    assert "BEGIN;" in sql
    assert sql.rstrip().endswith("COMMIT;")


@pytest.mark.parametrize("filename", FILES)
def test_analyse_fonctions_plpgsql(filename):
    sql = (ROOT / "sql" / filename).read_text(encoding="utf-8")
    fonctions = [
        stmt for stmt in pglast.split(sql)
        if stmt.lstrip().upper().startswith("CREATE OR REPLACE FUNCTION")
    ]
    # Pas de fonctions dans le registre 012 ; 013+ doivent avoir au moins une.
    if not filename.startswith("012"):
        assert fonctions
    for statement in fonctions:
        resultat = pglast.parse_plpgsql(statement)
        assert resultat
