"""Préparation non exécutable d'un dossier de régularisation d'inventaire.

Jamais d'appel à erp_apply_stock_movement, de changement de lot ou de création
d'écriture SCF. Les quantités restent des constats non homologués jusqu'à
preuve qualité, traçabilité par lot et délégation d'approbation.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from modules.stocks.inventory_service import InventoryError, lot_reconciliation


def _valid(raw: object, label: str) -> Decimal:
    try:
        v = Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise InventoryError(f"{label} invalide") from exc
    if not v.is_finite() or v < 0 or v >= Decimal("1e15"):
        raise InventoryError(f"{label} invalide")
    return v


def build_adjustment_preparation(
    campaign: dict, lines: list[dict], lots: list[dict],
) -> dict:
    """Liste les ajustements potentiels et les verrous, sans mutation."""
    if not isinstance(campaign, dict) or not campaign.get("inventaire_id"):
        raise InventoryError("Campagne à rapprocher absente")
    if not isinstance(lines, list) or not isinstance(lots, list):
        raise InventoryError("Photographie inventaire invalide")
    reconciliation = lot_reconciliation(lines, lots)
    blockers = []
    if campaign.get("statut") not in {"SANS_ECART", "ECARTS_A_QUALIFIER"}:
        blockers.append("Campagne non approuvée par un second acteur habilité")
    if not campaign.get("valide_par"):
        blockers.append("Acte de validation indépendant absent")
    if reconciliation["articles_non_reconcilies"]:
        blockers.append(
            f"{reconciliation['articles_non_reconcilies']} articles avec lots non réconciliés"
        )
    if reconciliation["lots_non_comptes"]:
        blockers.append(
            f"{reconciliation['lots_non_comptes']} lots sans comptage physique"
        )
    rows = []
    for line in lines:
        actual = line.get("quantite_comptee")
        if actual is None:
            blockers.append("Comptage article incomplet")
            continue
        expected = _valid(line.get("quantite_theorique"), "Stock théorique")
        counted = _valid(actual, "Stock physique")
        delta = counted - expected
        if delta == 0:
            continue
        cost_raw = line.get("pmp_snapshot")
        cost = _valid(cost_raw, "PMP") if cost_raw is not None else None
        nature = line.get("nature_ecart") or "NON_QUALIFIE"
        if nature == "NON_QUALIFIE":
            blockers.append(f"Nature d'écart non qualifiée : {line.get('article_id')}")
        if not line.get("qualification_note"):
            blockers.append(f"Justificatif d'écart absent : {line.get('article_id')}")
        if cost is None:
            blockers.append(f"Coût historique/PMP non documenté : {line.get('article_id')}")
        rows.append({
            "inventaire_id": campaign["inventaire_id"],
            "type_article": line["type_article"],
            "article_id": line["article_id"],
            "operation_envisagee": "ENTREE" if delta > 0 else "SORTIE",
            "ecart_quantite": str(delta),
            "quantite_absolue": str(abs(delta)),
            "pmp_snapshot_dzd": str(cost) if cost is not None else None,
            "valeur_indicative_dzd": str(abs(delta) * cost) if cost is not None else None,
            "nature_ecart": nature,
            "reference_justification": line.get("qualification_note") or "",
            "statut_projet": "NON_EXECUTABLE",
        })
    if not rows:
        blockers.append("Aucun écart physique à régulariser")
    return {
        "lignes": rows,
        "blocages": list(dict.fromkeys(blockers)),
        "executable": False,
        "mouvements_stock_appliques": False,
    }
