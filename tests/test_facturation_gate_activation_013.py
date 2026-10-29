"""Contrôle statique bloquant de pré-déploiement fiscal SQL 013.

Le SQL 013 n'est pas autorisé au déploiement tant que la classification
par SKU et les exigences de quittance ne sont pas codées et testées.
Ce fichier n'interroge pas la production et n'effectue aucune migration.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / "sql/013_facturation_parametree.sql").read_text(encoding="utf-8")
GUIDE = (ROOT / "docs/FACTURATION_BASCULE_PRECONDITIONS_2026.md").read_text(encoding="utf-8")


def test_deploiement_sql_013_explicitement_bloque():
    assert "BROUILLON : NON APPLICABLE" in SQL
    assert "NON ACTIVABLE en production" in GUIDE


def test_sql_013_sans_regle_universelle_activable_implicitement():
    # Le SQL actuel utilise un taux universel TVA_VENTE_TAUX, sans
    # classification fiscale produit. Le contrôle ci-dessous matérialise
    # cette lacune au lieu de présenter la migration comme opérationnelle.
    assert "erp_facture_parametre('TVA_VENTE_TAUX'" in SQL
    assert "erp_sku_fiscalite" not in SQL


def test_timbre_encore_calcule_sur_facture_dans_le_brouillon():
    # À retirer seulement avec un véritable moteur de quittances validé.
    assert "erp_facture_parametre('TIMBRE_ESPECES_TAUX'" in SQL
    assert "erp_facture_parametre('TIMBRE_ESPECES_PLAFOND'" in SQL
    assert "La base production" in GUIDE
