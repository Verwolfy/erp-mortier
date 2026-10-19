"""Authentification des utilisateurs ERP depuis PostgreSQL/Supabase.

Ne lit jamais les comptes ou les empreintes de mots de passe depuis Google Sheets.
"""
from __future__ import annotations

import logging

import bcrypt

_LOG = logging.getLogger(__name__)
# Coût amorti à l'import pour éviter de révéler l'existence d'un login par la
# durée de vérification. N'est associé à aucun compte réel.
_DUMMY_HASH = bcrypt.hashpw(b"login-inconnu-dummy", bcrypt.gensalt(rounds=12))


class AuthenticationBackendError(RuntimeError):
    """Le référentiel de comptes est momentanément inaccessible."""


def hash_password(password: str) -> str:
    """Produit une empreinte bcrypt pour un nouveau mot de passe."""
    if not isinstance(password, str) or not password or len(password.encode("utf-8")) > 72:
        raise ValueError("Mot de passe invalide (1 à 72 octets UTF-8 requis).")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("ascii")


def _is_active(value: object) -> bool:
    return value is True or str(value or "").strip().upper() in {
        "OUI", "TRUE", "1", "ACTIF", "ACTIVE", "YES"
    }


def authenticate_user(login: str, password_attempt: str) -> dict | None:
    """Authentifie un compte actif, sans divulguer son hash dans la session.

    Retourne None pour des identifiants invalides. Une panne SQL lève
    AuthenticationBackendError pour éviter de la compter comme mauvais mot de passe.
    """
    if not isinstance(login, str) or not isinstance(password_attempt, str):
        return None
    login = login.strip()
    if (not login or len(login) > 128 or not password_attempt or
            len(password_attempt.encode("utf-8")) > 72):
        return None

    try:
        from core.db_service import get_supabase_client
        response = (get_supabase_client().table("users")
                    .select("user_id,nom,login,hash_mdp,role,actif")
                    .eq("login", login).limit(2).execute())
        users = response.data or []
        if not isinstance(users, list):
            raise ValueError("Réponse de la base non conforme")
    except Exception as exc:
        _LOG.warning("Accès au référentiel de comptes impossible (%s)", type(exc).__name__)
        raise AuthenticationBackendError("Service d'authentification indisponible") from None

    # La colonne login est UNIQUE selon le schéma. En cas de donnée suspecte,
    # ne pas choisir arbitrairement une identité.
    if len(users) != 1 or not isinstance(users[0], dict):
        bcrypt.checkpw(password_attempt.encode("utf-8"), _DUMMY_HASH)
        return None

    account = users[0]
    stored = account.get("hash_mdp")
    try:
        if not isinstance(stored, str) or not stored.startswith(("$2a$", "$2b$", "$2y$")):
            return None
        valid = bcrypt.checkpw(password_attempt.encode("utf-8"), stored.encode("ascii"))
    except (ValueError, TypeError, UnicodeError):
        _LOG.warning("Empreinte de mot de passe non conforme")
        return None

    user_id, role = account.get("user_id"), account.get("role")
    if (not valid or account.get("login") != login or
            not _is_active(account.get("actif")) or
            not isinstance(user_id, str) or not user_id.strip() or
            not isinstance(role, str) or not role.strip()):
        return None
    return {"user_id": user_id, "nom": account.get("nom") or "Utilisateur", "role": role}
