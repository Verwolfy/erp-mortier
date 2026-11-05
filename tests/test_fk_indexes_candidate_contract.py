"""Contrat statique du candidat d'index FK : aucun SQL de production exécuté."""
from pathlib import Path
import re

SQL = Path(__file__).resolve().parents[1] / "sql/supabase_pending/erp_034_fk_indexes_CANDIDAT_NON_EXECUTE.sql"
EXPECTED = {
    ("controle_qualite", "of_id"),
    ("demandes_conges", "employe_id"),
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
PATTERN = re.compile(
    r"^CREATE INDEX CONCURRENTLY IF NOT EXISTS "
    r"([a-z_][a-z_0-9]*) ON public\.([a-z_][a-z_0-9]*) "
    r"\(([a-z_][a-z_0-9]*)\);$"
)


def test_candidate_has_exactly_15_unique_fk_indexes():
    lines = [
        line.strip()
        for line in SQL.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("--")
    ]
    assert len(lines) == len(EXPECTED)
    matches = [PATTERN.fullmatch(line) for line in lines]
    assert all(matches), "Seuls les CREATE INDEX CONCURRENTLY attendus sont autorisés"
    identifiers = [(m.group(1), m.group(2), m.group(3)) for m in matches]
    assert len({index_name for index_name, _, _ in identifiers}) == len(EXPECTED)
    assert {(table, column) for _, table, column in identifiers} == EXPECTED


def test_candidate_is_explicitly_not_executed():
    text = SQL.read_text(encoding="utf-8")
    assert "CANDIDAT NON EXECUTE" in text
    assert "hors transaction" in text
    assert "Ne pas lancer automatiquement" in text
