"""Verrou préalable aux futurs tests d'intégration *avec écriture*.

Ce module ne crée pas de client, ne lit aucun secret et ne lance aucun SQL.
Il protège la connexion à venir, même si le runner est invoqué par erreur avec
une configuration PRODUCTION. Une DB TEST distincte reste à provisionner.
"""
from __future__ import annotations

from collections.abc import Mapping

from core.environment_guard import (
    EnvironmentSafetyError, policy_from_environment, require_supabase_target,
)

_CONFIRM = "I_CONFIRM_SEPARATE_TEST_DATABASE"


def require_integration_test_target(environ: Mapping[str, str]) -> str:
    """Valide avant tout réseau : cible TEST, confirmation et variables cohérentes.

    Le retour est volontairement limité à 'TEST' : ne jamais journaliser les
    URLs de connexion, les clés API ou les données fournies par l'appelant.
    """
    if not isinstance(environ, Mapping):
        raise EnvironmentSafetyError("Configuration d'intégration absente")
    if environ.get("ERP_ENV") != "TEST":
        raise EnvironmentSafetyError("Intégration avec écriture interdite hors TEST")
    if environ.get("ERP_INTEGRATION_CONFIRM") != _CONFIRM:
        raise EnvironmentSafetyError("Confirmation explicite du bac TEST requise")

    # require_supabase_target vérifie aussi que les URL PROD et TEST sont
    # distinctes, en HTTPS cloud et sans chemin, paramètres ou credentials.
    policy = policy_from_environment(environ)
    target = environ.get("ERP_INTEGRATION_SUPABASE_URL")
    if require_supabase_target(policy, target) != "TEST":
        raise EnvironmentSafetyError("Bac d'intégration différent de TEST")

    # Refuser toute variable générique déjà configurée vers la production.
    # Certaines bibliothèques privilégient ces noms à l'URL dédiée.
    for name in ("SUPABASE_URL", "ERP_RUNTIME_SUPABASE_URL"):
        alias = environ.get(name)
        if alias not in (None, "") and require_supabase_target(policy, alias) != "TEST":
            raise EnvironmentSafetyError("Alias Supabase non autorisé pour TEST")

    # Ne jamais accepter que le même secret soit explicitement déclaré à la
    # fois pour TEST et PROD. Les valeurs ne doivent jamais être loguées.
    test_key = environ.get("ERP_TEST_SUPABASE_KEY")
    prod_key = environ.get("ERP_PRODUCTION_SUPABASE_KEY")
    if not isinstance(test_key, str) or not test_key.strip():
        raise EnvironmentSafetyError("Clé spécifique TEST manquante")
    if prod_key and test_key == prod_key:
        raise EnvironmentSafetyError("Clés TEST et PRODUCTION identiques")

    # La démo mémorielle n'est pas un substitut à un vrai projet TEST.
    return "TEST"
