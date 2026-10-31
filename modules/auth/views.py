"""Page de connexion Streamlit de l'ERP."""
import time
import logging

import streamlit as st

from modules.auth.service import AuthenticationBackendError, authenticate_user
_LOG = logging.getLogger(__name__)

from core.auth_rate_limit import (
    AuthRateLimitUnavailable,
    begin_login_attempt,
    finish_login_attempt,
)


def show_login_page():
    """Affiche la connexion et le ralentissement local à la session courante.

    Attention : la limite locale n'est pas une protection globale anti-bruteforce.
    Une limitation partagée (IP/compte) doit être déployée côté serveur.
    """
    st.title("🔐 Connexion ERP")
    st.markdown("Veuillez vous identifier pour accéder au système.")

    st.session_state.setdefault("login_attempts", 0)
    st.session_state.setdefault("lockout_time", 0)
    now = time.time()
    if st.session_state["lockout_time"] > now:
        remaining = max(1, int(st.session_state["lockout_time"] - now))
        st.error(f"⚠️ Trop de tentatives. Veuillez patienter {remaining} secondes.")
        return
    if st.session_state["lockout_time"] > 0:
        st.session_state["login_attempts"] = 0
        st.session_state["lockout_time"] = 0

    with st.form("login_form"):
        login = st.text_input("Identifiant (Login)", autocomplete="username")
        password = st.text_input("Mot de passe", type="password", autocomplete="current-password")
        submitted = st.form_submit_button("Se connecter", type="primary", use_container_width=True)

    if not submitted:
        return
    if not login or not password:
        st.warning("Veuillez remplir tous les champs.")
        return

    # Autorisation partagee avant toute verification du mot de passe.
    try:
        token = begin_login_attempt(login)
    except AuthRateLimitUnavailable:
        _LOG.error("ERP_AUTH_STAGE=BEGIN_UNAVAILABLE")
        st.error("Connexion temporairement indisponible (AUTH-01). Réessayez plus tard.")
        return

    if token is None:
        st.error("Connexion temporairement bloqu?e ou d?j? en cours. R?essayez plus tard.")
        return

    try:
        user_data = authenticate_user(login, password)
    except Exception as exc:
        _LOG.error("ERP_AUTH_STAGE=ACCOUNT_UNAVAILABLE type=%s", type(exc).__name__)
        # Une erreur technique ne doit pas compter comme mauvais mot de passe.
        try:
            finish_login_attempt(token, "BACKEND_ERROR")
        except AuthRateLimitUnavailable:
            _LOG.error("ERP_AUTH_STAGE=ERROR_FINALIZE_UNAVAILABLE")
        st.error("Connexion temporairement indisponible (AUTH-02). Réessayez plus tard.")
        return

    # La session ne sera ouverte qu'apres confirmation de Supabase.
    try:
        finish_login_attempt(token, "SUCCESS" if user_data else "FAILURE")
    except AuthRateLimitUnavailable:
        _LOG.error("ERP_AUTH_STAGE=FINISH_UNAVAILABLE")
        st.error("Connexion temporairement indisponible (AUTH-03). Réessayez plus tard.")
        return

    if user_data:
        st.session_state["login_attempts"] = 0
        st.session_state["lockout_time"] = 0
        st.session_state["user"] = user_data
        st.session_state["authenticated"] = True
        st.session_state["last_activity"] = time.time()
        st.success(f"Bienvenue, {user_data['nom']} !")
        st.rerun()
        return

    st.session_state["login_attempts"] += 1
    if st.session_state["login_attempts"] >= 3:
        st.session_state["lockout_time"] = time.time() + 180
        st.error("Trop de tentatives échouées. Veuillez réessayer dans 3 minutes.")
        return
    st.error("Identifiants incorrects ou compte inactif.")


def logout():
    """Termine la session sans vider les caches globaux."""
    st.session_state["user"] = None
    st.session_state["authenticated"] = False
    st.session_state["last_activity"] = 0
    st.session_state["login_attempts"] = 0
    st.session_state["lockout_time"] = 0
    st.rerun()
