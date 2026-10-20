"""Point d'entrée de l'ERP Streamlit (Supabase est la source de vérité).

La connexion est créée par modules.auth.views. Sur chaque chargement de page,
l'identité et le rôle sont revérifiés dans PostgreSQL avant d'afficher les vues.
La protection des écritures demeure obligatoire dans les services métier.
"""
from __future__ import annotations

import logging
import math
import time

import streamlit as st

# Doit rester le premier appel à l'API Streamlit dans le script.
st.set_page_config(
    page_title="ERP Mortier & Adjuvants",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

from config.roles import get_allowed_modules, has_permission
from modules.auth.views import logout, show_login_page

_LOG = logging.getLogger(__name__)
TIMEOUT_SECONDS = 1800  # 30 minutes, compatible avec auth/views.py

# Les intitulés de modules ont une casse normalisée pour le menu.
_MENU_LABELS = {
    "Administration": "⚙️ Administration",
    "Achats": "🛒 Achats & Appro.",
    "Stocks": "📦 Stocks",
    "Production": "🏭 Production",
    "Ventes": "🧾 Ventes & Facturation",
    "CRM": "🤝 CRM",
    "Finance": "🏦 Comptabilité & Finances",
    "RH": "👥 Ressources Humaines",
    "Dashboards": "📊 Tableaux de bord",
}
_ACTIVE_VALUES = frozenset({"OUI", "TRUE", "1", "ACTIF", "ACTIVE", "YES"})


def _active(value: object) -> bool:
    """Interprète strictement les statuts historiques (texte ou booléen)."""
    if value is True or value == 1:
        return True
    return isinstance(value, str) and value.strip().upper() in _ACTIVE_VALUES


def _session_expired(last_activity: object, now: float) -> bool:
    """Refuse les horodatages invalides, futurs ou expirés (y compris NaN)."""
    if (isinstance(last_activity, bool) or
            not isinstance(last_activity, (int, float))):
        return True
    stamp = float(last_activity)
    return not math.isfinite(stamp) or stamp > now or now - stamp > TIMEOUT_SECONDS


def _fetch_active_user(user_id: str) -> dict[str, str] | None:
    """Interroge Supabase pour confirmer le compte et obtenir son rôle actuel.

    Une erreur réseau est propagée au caller : elle ne vaut jamais validation.
    Les empreintes de mot de passe ne sont jamais récupérées pour le menu.
    """
    from core.db_service import get_supabase_client

    result = (
        get_supabase_client()
        .table("users")
        .select("user_id,nom,role,actif")
        .eq("user_id", user_id)
        .limit(2)
        .execute()
    )
    rows = result.data
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        return None
    account = rows[0]
    account_id = account.get("user_id")
    role = account.get("role")
    if (account_id != user_id or not _active(account.get("actif")) or
            not isinstance(role, str) or not role.strip()):
        return None
    return {
        "user_id": user_id,
        "nom": str(account.get("nom") or "Utilisateur"),
        "role": role.strip(),
    }


def _verified_user(now: float) -> dict[str, str] | None:
    """Vérifie la session et le rôle Supabase ; n'accorde jamais un accès incertain."""
    current = st.session_state.get("user")
    user_id = current.get("user_id") if isinstance(current, dict) else None
    if not isinstance(user_id, str) or not user_id.strip():
        st.warning("Session invalide. Veuillez vous reconnecter.")
        logout()
        return None

    if _session_expired(st.session_state.get("last_activity"), now):
        st.warning("Votre session a expiré pour cause d'inactivité. Veuillez vous reconnecter.")
        logout()
        return None

    try:
        account = _fetch_active_user(user_id)
    except Exception as exc:
        # Pas d'exception brute ni de données confidentielles sur l'interface.
        _LOG.warning("Vérification de session indisponible : %s", type(exc).__name__)
        st.error("Vérification de session indisponible. Réessayez dans quelques instants.")
        return None

    if account is None:
        st.warning("Compte désactivé ou session invalide. Veuillez vous reconnecter.")
        logout()
        return None

    st.session_state["user"] = account  # Remplace notamment un rôle obsolète en session.
    # Limite connue : tout rerun Streamlit est compté comme activité ; les
    # rafraîchissements automatiques nécessitent une gestion événementielle.
    st.session_state["last_activity"] = now
    return account


def _allowed_menu(role: str) -> dict[str, str]:
    """Construit le menu à partir des droits de lecture, avec contrôle séparé RH/administration."""
    modules = {
        name.strip().casefold() for name in get_allowed_modules(role)
        if isinstance(name, str)
    }
    menu: dict[str, str] = {}
    for name, label in _MENU_LABELS.items():
        if name.casefold() not in modules:
            continue
        menu[name] = label
        if name == "Administration" and has_permission(role, "Administration", "ecriture"):
            # Conserver l'ordre de navigation historique : Sécurité après Admin.
            menu["Securite"] = "🔐 Utilisateurs & Sécurité"
    menu["Help"] = "📚 Guide & Aide"
    return menu


def _render_menu_page(choice: str | None, role: str) -> None:
    """Charge uniquement la vue autorisée. Le service métier contrôle les écritures."""
    if choice == "Administration":
        from modules.admin.views import show_admin_page
        show_admin_page()
    elif choice == "Securite":
        # Seule l'administration en écriture peut atteindre cette page.
        if not has_permission(role, "Administration", "ecriture"):
            st.error("Accès non autorisé.")
            return
        from modules.admin.views import show_user_management
        show_user_management()
    elif choice == "Achats":
        from modules.achats.views import show_achats_page
        show_achats_page()
    elif choice == "Stocks":
        from modules.stocks.views import show_stocks_page
        show_stocks_page()
    elif choice == "Production":
        from modules.production.views import show_production_page
        show_production_page()
    elif choice == "Ventes":
        from modules.ventes.views import show_ventes_page
        show_ventes_page()
    elif choice == "CRM":
        from modules.crm.views import show_crm_page
        show_crm_page()
    elif choice == "Finance":
        from modules.finance.views import show_finance_page
        show_finance_page()
    elif choice == "RH":
        from modules.rh.views import show_rh_page
        show_rh_page()
    elif choice == "Dashboards":
        from modules.dashboards.views import show_dashboards_page
        show_dashboards_page()
    elif choice == "Help":
        from modules.help.views import show_help_page
        show_help_page()


def main() -> None:
    st.session_state.setdefault("authenticated", False)
    st.session_state.setdefault("user", None)

    if st.session_state["authenticated"] is not True:
        show_login_page()
        return

    user = _verified_user(time.time())
    if user is None:
        return
    role = user["role"]

    try:
        menu_options = _allowed_menu(role)
    except Exception as exc:
        _LOG.warning("Impossible de charger les droits de menu : %s", type(exc).__name__)
        st.error("Chargement des autorisations indisponible.")
        return

    with st.sidebar:
        st.write(f"👤 **{user['nom']}**")
        st.caption(f"Rôle : {role}")
        if st.button("🚪 Déconnexion", use_container_width=True):
            logout()
            return
        st.divider()
        st.subheader("Navigation")
        choice = st.radio(
            "Aller vers :", list(menu_options),
            format_func=lambda name: menu_options[name],
        )

    # Un choix Streamlit ne doit jamais donner accès à une page hors du menu.
    if choice not in menu_options:
        st.error("Accès non autorisé.")
        return
    _render_menu_page(choice, role)


if __name__ == "__main__":
    main()
