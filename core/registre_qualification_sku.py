"""Registre de revue fiscale SKU, sans affectation automatique de catégorie TVA.

Entrées : liste de SKU actifs issue d'une lecture autorisée (pas de connexion
ou écriture SQL ici). Sortie : Markdown de travail à compléter et valider.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def _cell(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Champ SKU obligatoire ou invalide")
    if any(ord(char) < 32 for char in value):
        raise ValueError("Caractère de contrôle dans le référentiel SKU")
    return value.strip().replace("|", r"\|")


def registre_qualification_sku(skus: Sequence[Mapping[str, Any]]) -> str:
    """Construit un registre sans inventer TVA, exonération, dates ou sources."""
    if not isinstance(skus, (list, tuple)):
        raise ValueError("Liste de SKU invalide")
    rows: list[tuple[str, str, str, str]] = []
    seen: set[str] = set()
    for item in skus:
        if not isinstance(item, Mapping):
            raise ValueError("Ligne de SKU invalide")
        sku, pf, fmt, unite = (
            _cell(item.get("sku_id")),
            _cell(item.get("pf_id")),
            _cell(item.get("format")),
            _cell(item.get("unite_vente")),
        )
        if sku in seen:
            raise ValueError("SKU dupliqué")
        seen.add(sku)
        rows.append((sku, pf, fmt, unite))
    rows.sort()
    lines = [
        "# Registre de qualification fiscale des SKU actifs",
        "",
        "**Document de travail non homologué.** Aucun taux, catégorie TVA,",
        "exonération, date d'effet ni source juridique n'est présumé.",
        "Ne pas importer ces lignes comme classifications validées.",
        "",
        "| SKU | Produit | Format | Unité | État de revue | Catégorie TVA | Référence juridique | Date d'effet | Validateur |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for sku, pf, fmt, unite in rows:
        lines.append(
            f"| {sku} | {pf} | {fmt} | {unite} | À qualifier | — | — | — | — |"
        )
    lines.extend([
        "",
        f"**Couverture : 0/{len(rows)} classifications approuvées dans ce registre.**",
        "",
        "Avant tout enregistrement dans `erp_sku_fiscalite`, documenter",
        "la catégorie, le code de paramètre le cas échéant, les textes",
        "applicables, leur justification, les dates d'effet et de vérification,",
        "l'identité du valideur et la date de validation.",
        "Une classification ne vaut pas autorisation de mise en service :",
        "le régime de l'entreprise, le timbre des quittances et la RPC",
        "transactionnelle restent des prérequis distincts.",
        "",
    ])
    return "\n".join(lines)
