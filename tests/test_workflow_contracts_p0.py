"""Contrats P0 : empreinte statique des transitions réellement codées.

Ce test vérifie la présence des gardes dans le SQL versionné, sans exécuter
de migration ni prétendre prouver les comportements du serveur de production.
Les tests unitaires RPC existants et une future DB TEST couvrent le runtime.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Basé exclusivement sur les RPC SQL existantes (pas de règles imaginées).
SQL_GUARDS = {
    "Achat -> EN_ATTENTE": (
        "sql/004_atomic_purchases.sql",
        ("VALUES(p_order_id,v_now", "'EN_ATTENTE');",
         "ON CONFLICT (operation_id) DO NOTHING"),
    ),
    "Réception achat partielle ou complète": (
        "sql/004_atomic_purchases.sql",
        ("v_order.statut NOT IN ('EN_ATTENTE','PARTIELLEMENT_RECEPTIONNE')",
         "Statut de commande non réceptionnable",
         "THEN 'RECEPTIONNE' ELSE 'PARTIELLEMENT_RECEPTIONNE'",
         "p_commande_achat_id FOR UPDATE"),
    ),
    "Facture brouillon": (
        "sql/005_atomic_sales.sql",
        ("IF p_action = 'DRAFT' THEN",
         "'statut','BROUILLON'", "ON CONFLICT (operation_id) DO NOTHING"),
    ),
    "Facture validée ou annulée uniquement depuis brouillon": (
        "sql/005_atomic_sales.sql",
        ("ELSIF p_action IN ('VALIDATE','CANCEL') THEN",
         "v_invoice.statut IS DISTINCT FROM 'BROUILLON'",
         "Seuls les brouillons peuvent être validés ou annulés",
         "THEN 'VALIDE' ELSE 'ANNULE' END"),
    ),
    "Expédition et contrôle du disponible": (
        "sql/005_atomic_sales.sql",
        ("ELSIF p_action='SHIP' THEN",
         "'PARTIELLEMENT_LIVREE'",
         "Quantité expédiée supérieure à la commande",
         "erp_apply_stock_movement("),
    ),
    "OF planifié -> en cours": (
        "sql/003_atomic_manufacturing_close.sql",
        ("IF v_status = 'PLANIFIE' THEN",
         "SET statut = 'EN_COURS'",
         "ELSIF v_status <> 'EN_COURS' THEN",
         "Transition impossible : OF non planifié ou déjà clos"),
    ),
    "OF planifié/en cours -> terminé ou rejeté": (
        "sql/003_atomic_manufacturing_close.sql",
        ("v_of.statut NOT IN ('PLANIFIE', 'EN_COURS')",
         "OF non clôturable dans cet état",
         "THEN 'TERMINE' ELSE 'REJETE' END",
         "erp_of_closures"),
    ),
    "Règlement valide -> lettrage": (
        "sql/006_atomic_finance.sql",
        ("v_payment.statut IS DISTINCT FROM 'VALIDE'",
         "v_invoice.statut IS DISTINCT FROM 'VALIDE'",
         "v_applied+v_amount>v_payment.montant_total",
         "Facture déjà réglée ou montant de règlement supérieur"),
    ),
    "Sortie stock FIFO sans quantité négative": (
        "sql/002_atomic_stock_movement.sql",
        ("Stock global insuffisant",
         "ORDER BY date_creation ASC NULLS LAST, lot_id ASC",
         "FOR UPDATE",
         "Incohérence globale / somme des lots"),
    ),
}

SERVICE_ENTRYPOINTS = {
    "modules/achats/service.py": (
        "create_commande_achat", "creer_bon_reception"),
    "modules/ventes/service.py": (
        "create_facture_brouillon", "valider_facture",
        "annuler_facture", "creer_bon_livraison"),
    "modules/production/service.py": (
        "changer_statut_of", "enregistrer_controle_qualite"),
    "modules/finance/service.py": ("enregistrer_lettrage",),
    "modules/stocks/service.py": (
        "enregistrer_sortie_mp", "enregistrer_sortie_pf"),
}


@pytest.mark.parametrize("name,path,guards",
                         [(name, *contract) for name, contract in SQL_GUARDS.items()])
def test_transaction_workflow_sql_guards_present(name, path, guards):
    sql = (ROOT / path).read_text(encoding="utf-8")
    for fragment in guards:
        assert fragment in sql, f"{name}: garde supprimée : {fragment}"


@pytest.mark.parametrize("path,names", SERVICE_ENTRYPOINTS.items())
def test_workflow_service_entrypoints_remain_available(path, names):
    script = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    functions = {node.name for node in script.body
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert set(names) <= functions


def test_contracts_are_static_not_automatic_production_permissions():
    assert "sql/005_atomic_sales.sql" in {x[0] for x in SQL_GUARDS.values()}
    # Pas d'exécution SQL, d'accès Supabase, ni de données fictives persistées.
    text = (ROOT / "docs" / "CONTRATS_WORKFLOWS_P0_20261108.md").read_text(encoding="utf-8")
    assert "Ne constitue pas une preuve de déploiement" in text
    assert "PostgreSQL production" in text
