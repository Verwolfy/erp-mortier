"""Migration 010-A-01 : isolation TEST/PRODUCTION, sans accès réseau.

Les déclarations attendues doivent provenir de secrets du déploiement distincts
pour chaque environnement. Une configuration absente ou ambiguë bloque l'accès.
Ce verrou ne remplace PAS les contrôles RBAC/RLS, ni la séparation des comptes
et ressources dans les fournisseurs Supabase / Google.
"""
from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urlsplit


class EnvironmentSafetyError(RuntimeError):
    """Arrêt préventif avant une connexion potentiellement dangereuse."""


def _canonical_supabase_url(value: object) -> str:
    """Accepte uniquement l'URL racine HTTPS d'un projet Supabase cloud."""
    if not isinstance(value, str) or not value.strip():
        raise EnvironmentSafetyError("URL de projet Supabase absente ou invalide")
    try:
        parsed = urlsplit(value.strip())
        host = parsed.hostname or ""
        has_port = parsed.port is not None
    except ValueError as exc:
        raise EnvironmentSafetyError("URL Supabase mal formée") from exc
    prefix = host.removesuffix(".supabase.co")
    if (parsed.scheme != "https" or not host.endswith(".supabase.co")
            or not prefix or not prefix.isascii()
            or not prefix.replace("-", "").isalnum()
            or prefix.lower() != prefix or parsed.username is not None
            or parsed.password is not None or has_port
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise EnvironmentSafetyError("URL Supabase refusée : projet HTTPS attendu")
    return f"https://{host}"


def _policy(config: object) -> tuple[str, str | None, str]:
    if not isinstance(config, Mapping):
        raise EnvironmentSafetyError("Configuration d'environnement manquante")
    name = config.get("name")
    if name not in ("TEST", "PRODUCTION"):
        raise EnvironmentSafetyError("Environnement non déclaré : TEST ou PRODUCTION requis")
    prod_url = _canonical_supabase_url(config.get("production_supabase_url"))
    # Le seul projet utilisé aujourd'hui est PRODUCTION. Ne pas imposer
    # l'existence ni la configuration d'un ancien projet TEST supprimable.
    value = config.get("test_supabase_url")
    test_url = _canonical_supabase_url(value) if value not in (None, "") else None
    if name == "TEST" and test_url is None:
        raise EnvironmentSafetyError("Projet TEST absent : configuration refusée")
    if test_url is not None and test_url == prod_url:
        raise EnvironmentSafetyError("Les environnements doivent être distincts")
    if name == "PRODUCTION" and config.get("production_enabled") is not True:
        raise EnvironmentSafetyError("PRODUCTION désactivée : autorisation explicite requise")
    return name, test_url, prod_url


def require_supabase_target(config: object, active_url: object) -> str:
    """Vérifie l'URL avant l'instanciation de tout client Supabase."""
    name, test_url, prod_url = _policy(config)
    expected = test_url if name == "TEST" else prod_url
    if _canonical_supabase_url(active_url) != expected:
        raise EnvironmentSafetyError("Projet Supabase différent du projet autorisé")
    return name


def require_sheet_id(config: object, active_supabase_url: object,
                     module: str, production_ids: Mapping[str, str]) -> str:
    """Isole les classeurs TEST et PROD et refuse un ID TEST connu en PROD."""
    name = require_supabase_target(config, active_supabase_url)
    if module not in production_ids:
        raise EnvironmentSafetyError("Module Google Sheets non référencé")
    if name == "PRODUCTION":
        sheet_id = production_ids[module]
    else:
        test_ids = config.get("test_sheets_ids")
        if not isinstance(test_ids, Mapping):
            raise EnvironmentSafetyError("Classeur TEST non configuré")
        sheet_id = test_ids.get(module)
        if sheet_id in production_ids.values():
            raise EnvironmentSafetyError("Classeur TEST identique à un classeur PRODUCTION")
    if not isinstance(sheet_id, str) or not sheet_id.strip():
        raise EnvironmentSafetyError("Identifiant de classeur absent")
    return sheet_id


def policy_from_streamlit(secrets: Mapping) -> Mapping:
    """Ne traite jamais les clés ou mots de passe ; récupère seulement la politique."""
    try:
        config = secrets["erp_environment"]
    except (KeyError, TypeError) as exc:
        raise EnvironmentSafetyError("Politique ERP absente de Streamlit Secrets") from exc
    if not isinstance(config, Mapping):
        raise EnvironmentSafetyError("Politique ERP invalide")
    return config


def policy_from_environment(environ: Mapping[str, str]) -> dict[str, object]:
    """Utilisation par les tâches Python exécutées hors de Streamlit."""
    return {
        "name": environ.get("ERP_ENV"),
        "test_supabase_url": environ.get("ERP_TEST_SUPABASE_URL"),
        "production_supabase_url": environ.get("ERP_PRODUCTION_SUPABASE_URL"),
        "production_enabled": environ.get("ERP_PRODUCTION_ENABLED") == "true",
    }
