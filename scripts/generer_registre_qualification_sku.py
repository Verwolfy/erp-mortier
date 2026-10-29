"""Génère hors ligne un registre de qualification des SKU actifs.

Usage:
    python scripts/generer_registre_qualification_sku.py \
        --entree sku_actifs.json --sortie revue_tva_sku.md

Le JSON d'entrée est une liste de {sku_id, pf_id, format, unite_vente},
obtenue par une lecture autorisée. Aucune connexion à la BDD, aucun taux
fiscal présumé, aucune écriture SQL.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.registre_qualification_sku import registre_qualification_sku


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entree", required=True, type=Path)
    parser.add_argument("--sortie", required=True, type=Path)
    options = parser.parse_args(argv)
    rows = json.loads(options.entree.read_text(encoding="utf-8"))
    rendu = registre_qualification_sku(rows)
    options.sortie.write_text(rendu, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
