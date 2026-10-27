"""Limitation partagee des authentifications via RPC Supabase."""

from uuid import UUID

from core.db_service import get_supabase_client


class AuthRateLimitUnavailable(RuntimeError):
    pass


def begin_login_attempt(login: str) -> str | None:
    # None signifie refus ou blocage de la tentative.
    if not isinstance(login, str) or not login.strip() or len(login.strip()) > 128:
        return None

    try:
        data = (
            get_supabase_client()
            .rpc("erp_auth_begin", {"p_login": login.strip()})
            .execute()
            .data
        )
        if data is None:
            return None
        if not isinstance(data, str):
            raise ValueError("Jeton invalide")
        UUID(data)
        return data
    except Exception:
        raise AuthRateLimitUnavailable(
            "Protection des connexions indisponible"
        ) from None


def finish_login_attempt(token: str, outcome: str) -> None:
    if outcome not in ("SUCCESS", "FAILURE", "BACKEND_ERROR"):
        raise ValueError("Resultat interdit")

    UUID(token)

    try:
        result = (
            get_supabase_client()
            .rpc(
                "erp_auth_finish",
                {"p_token": token, "p_outcome": outcome},
            )
            .execute()
            .data
        )
        if result is not True:
            raise ValueError("Finalisation non confirmee")
    except Exception:
        raise AuthRateLimitUnavailable(
            "Finalisation de connexion indisponible"
        ) from None
