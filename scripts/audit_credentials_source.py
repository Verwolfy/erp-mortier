"""Contrôle statique des affectations littérales de secrets Python.

N'affiche jamais les valeurs détectées. Ne remplace pas un outil
d'analyse de l'historique Git comme gitleaks.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

SENSITIVE_NAME = re.compile(r"(?:password|passwd|mot_de_passe|secret|api_key|token)", re.I)


def suspicious_assignment_lines(source: str) -> list[int]:
    """Détecte les affectations directes de chaînes ou nombres non vides."""
    found: set[int] = set()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign):
            targets, value = [node.target], node.value
        if not isinstance(value, ast.Constant):
            continue
        if not isinstance(value.value, (str, bytes, int)) or not value.value:
            continue
        if any(
            isinstance(target, ast.Name) and SENSITIVE_NAME.search(target.id)
            for target in targets
        ):
            found.add(node.lineno)
    return sorted(found)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("Usage : python scripts/audit_credentials_source.py <fichier_python>")
        return 2
    path = Path(args[0])
    try:
        lines = suspicious_assignment_lines(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeError):
        print("Échec : fichier source indisponible ou invalide")
        return 2
    if lines:
        print(
            f"REFUS : {len(lines)} affectation(s) suspectes dans {path.name} "
            f"lignes {', '.join(map(str, lines))} (valeurs masquées)"
        )
        return 1
    print(f"OK : aucune affectation sensible littérale dans {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
