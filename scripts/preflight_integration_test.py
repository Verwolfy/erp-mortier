"""Précontrôle isolé des tests d'intégration — aucune connexion réseau.

Usage futur (après création d'un vrai projet TEST séparé) :
    python scripts/preflight_integration_test.py

Code 0 : configuration autorisée pour TEST ; code 2 : refus.
Ce script est un GATE, il ne lance pas les tests ni de migration.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Compatible avec 'python scripts/...' depuis la racine du dépôt.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.environment_guard import EnvironmentSafetyError
from core.integration_test_guard import require_integration_test_target


def main() -> int:
    try:
        require_integration_test_target(os.environ)
    except EnvironmentSafetyError:
        # Ne jamais afficher la valeur du champ en faute (URL, clé, token).
        print("REFUS : intégration interdite sans projet TEST distinct et explicite")
        return 2
    print("AUTORISÉ : précontrôle TEST validé ; aucune connexion effectuée")
    return 0


if __name__ == "__main__":
    sys.exit(main())
