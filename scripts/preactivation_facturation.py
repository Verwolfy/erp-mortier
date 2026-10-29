"""Verrou de préactivation de la migration 013 (échec fermé).

Ce script n'exécute aucun SQL. Il exige un manifeste d'homologation réel,
et refuse systématiquement le brouillon SQL 013 connu comme non conforme
au processus par SKU / quittances. Il ne valide pas l'application fiscale.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def verifier_migration(path: Path) -> None:
    if path.name == "013_facturation_parametree.sql":
        raise RuntimeError(
            "SQL 013 est un brouillon non activable : TVA universelle, "
            "classification SKU et fiscalité des quittances non implémentées"
        )
    raise RuntimeError(
        "Migration de facturation non homologuée : créer une procédure dédiée "
        "avec preuves fiscales, tests SQL/Python et revue des droits"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("migration", type=Path)
    args = parser.parse_args(argv)
    try:
        verifier_migration(args.migration)
    except RuntimeError as exc:
        print(f"REFUS PRÉACTIVATION : {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
