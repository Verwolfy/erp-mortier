"""Contrats du diagnostic fiscal : une seule requête SELECT sans DDL/DML."""
from pathlib import Path

import pytest

pglast = pytest.importorskip("pglast")

SQL = Path(__file__).resolve().parents[1] / (
    "sql/audits/fiscal_sales_readiness_readonly_20261109.sql"
)


def test_requete_fiscal_readiness_une_seule_lecture():
    source = SQL.read_text(encoding="utf-8")
    statements = pglast.parse_sql(source)
    assert len(statements) == 1
    assert type(statements[0].stmt).__name__ == "SelectStmt"
    assert statements[0].stmt.withClause is not None
    assert "FOR UPDATE" not in source.upper()
    assert "FOR SHARE" not in source.upper()


@pytest.mark.parametrize("field", [
    "TVA_TAUX_NORMAL",
    "TVA_TAUX_REDUIT",
    "TVA_VENTE_TAUX",
    "lignes_a_valider",
    "lignes_validees_applicables",
    "skus_actifs_sans_classement_valide",
    "fonction_parametre_deployee",
    "fonction_vente_deployee",
    "rpc_contient_anciens_litteraux",
    "homologation_reglementaire_automatique",
])
def test_diagnostic_expose_les_verrous_necessaires(field):
    assert field in SQL.read_text(encoding="utf-8")


def test_diagnostic_ne_peut_pas_auto_homologuer():
    source = SQL.read_text(encoding="utf-8")
    assert "false AS homologation_reglementaire_automatique" in source
    assert "erp_sku_fiscalite" in source
    assert "statut = 'VALIDEE'" in source
    assert "public.parametres_reglementaires" in source
