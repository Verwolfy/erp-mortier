"""Page de connexion Streamlit de l'ERP."""
import time

import streamlit as st

from modules.auth.service import AuthenticationBackendError, authenticate_user


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

    try:
        user_data = authenticate_user(login, password)
    except AuthenticationBackendError:
        st.error("Connexion temporairement indisponible. Veuillez réessayer plus tard.")
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
    """Termine la session ; conserve la purge de cache historique de l’ERP.

    Le cache global doit être revu pour isoler les données par utilisateur
    avant de supprimer cette purge, coûteuse pour les autres sessions.
    """
    st.session_state["user"] = None
    st.session_state["authenticated"] = False
    st.session_state["last_activity"] = 0
    st.session_state["login_attempts"] = 0
    st.session_state["lockout_time"] = 0
    st.cache_data.clear()
    st.rerun()
