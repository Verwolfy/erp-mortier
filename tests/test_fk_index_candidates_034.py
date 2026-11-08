"""Contrat statique du candidat ERP-034 : aucune écriture SQL, couverture FK datée.

Ces tests valident le fichier versionné, PAS l'efficacité d'index en production.
Le déploiement reste interdit sans essai sur la base de test et revue de charge.
"""
from __future__ import annotations

import re
from pathlib import Path

CANDIDAT = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "supabase_pending"
    / "erp_034_fk_indexes_CANDIDAT_NON_EXECUTE.sql"
)

INDEX_SQL = re.compile(
    r"CREATE INDEX CONCURRENTLY IF NOT EXISTS\s+(\w+)\s+ON\s+public\.(\w+)\s*\(\s*(\w+)\s*\)",
    re.IGNORECASE,
)

# Photographie de l'advisor Supabase au 2026-11-08 ; adapter seulement après
# contrôle en lecture seule des clés étrangères et des index réels.
EXPECTED_FK = {
    ("controle_qualite", "of_id"),
    ("demandes_conges", "employe_id"),
    ("erp_cost_drivers", "of_id"),
    ("erp_cost_of_validation_snapshot", "of_id"),
    ("erp_cost_pools", "nature_code"),
    ("erp_exonerations_tva_clients", "cree_par"),
    ("erp_exonerations_tva_evenements", "acteur_metier"),
    ("erp_exonerations_tva_operations", "acteur_id"),
    ("erp_exonerations_tva_operations", "attestation_id"),
    ("factures_fournisseurs", "commande_achat_id"),
    ("lettrage", "reglement_id"),
    ("lignes_achats", "commande_achat_id"),
    ("lignes_commande_ventes", "commande_vente_id"),
    ("lignes_devis", "devis_id"),
    ("lignes_facture", "facture_id"),
    ("lignes_recette", "recette_id"),
    ("ordres_fabrication", "recette_id"),
    ("sku_conditionnement", "pf_id"),
}


def _statements() -> list[str]:
    source = CANDIDAT.read_text(encoding="utf-8")
    return [
        stmt.strip()
        for stmt in "\n".join(
            line for line in source.splitlines()
            if line.strip() and not line.lstrip().startswith("--")
        ).split(";")
        if stmt.strip()
    ]


def test_candidat_fk_index_034_couvre_advisor_20261108():
    statements = _statements()
    assert len(statements) == len(EXPECTED_FK) == 18
    matches = [INDEX_SQL.fullmatch(statement) for statement in statements]
    assert all(matches), "Candidat non exclusivement additif / CREATE INDEX"
    names = [match.group(1) for match in matches]
    assert len(names) == len(set(names)), "Noms d'index dupliqués"
    actual = {(match.group(2), match.group(3)) for match in matches}
    assert actual == EXPECTED_FK, "Couverture FK manquante ou inattendue"
