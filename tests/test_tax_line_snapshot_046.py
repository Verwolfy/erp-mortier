"""Contrat statique ERP-046 : preuve de TVA par ligne, rétrocompatible."""
from pathlib import Path

import pytest

pglast = pytest.importorskip("pglast")
SQL = (Path(__file__).resolve().parents[1] /
       "sql/046_lignes_facture_preuve_tva_additive.sql").read_text(encoding="utf-8")


def test_sql_046_est_une_evolution_pg17_parsable():
    stmts = pglast.parse_sql(SQL)
    assert len(stmts) >= 4
    assert all(type(stmt.stmt).__name__ in ("AlterTableStmt", "CommentStmt")
               for stmt in stmts)


def test_sql_046_additif_et_sans_taux_legal_fixe():
    assert "ALTER TABLE public.lignes_facture" in SQL
    assert "ADD COLUMN IF NOT EXISTS code_regle_tva text" in SQL
    assert "ADD CONSTRAINT erp_lignes_facture_tva_snapshot_complet" in SQL
    assert "VALIDATE CONSTRAINT erp_lignes_facture_tva_snapshot_complet" in SQL
    assert "code_regle_tva IS NULL" in SQL
    assert "assiette_tva IS NULL" in SQL
    assert "code_regle_tva IN ('TVA_TAUX_NORMAL', 'TVA_TAUX_REDUIT')" in SQL
    assert "montant_tva_ligne = round(assiette_tva * taux_tva_ligne, 2)" in SQL
    assert "source_classification_tva" in SQL
    assert "date_verification_classification_tva" in SQL
    assert "date_effet_regle_tva <= date_fait_generateur_tva" in SQL
    assert "INSERT INTO" not in SQL.upper()
    assert "UPDATE public.factures" not in SQL
    assert "UPDATE public.lignes_facture" not in SQL
    assert "DROP " not in SQL.upper()
    assert "TRUNCATE " not in SQL.upper()
    assert "CREATE OR REPLACE FUNCTION public.erp_sale_transaction" not in SQL
