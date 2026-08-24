"""
Interface utilisateur pour l'authentification.
Intègre le Rate Limiting (Anti-Bruteforce) et la désactivation de l'autocomplétion.
"""
import time
import streamlit as st
from modules.auth.service import authenticate_user

def show_login_page():
    """Affiche le formulaire de connexion avec anti-bruteforce."""
    st.title("🔐 Connexion ERP")
    st.markdown("Veuillez vous identifier pour accéder au système.")

    # Initialisation du rate limiting
    if "login_attempts" not in st.session_state:
        st.session_state["login_attempts"] = 0
    if "lockout_time" not in st.session_state:
        st.session_state["lockout_time"] = 0

    # Vérification du blocage actuel
    current_time = time.time()
    if st.session_state["lockout_time"] > current_time:
        remaining = int(st.session_state["lockout_time"] - current_time)
        st.error(f"⚠️ Trop de tentatives. Votre compte est bloqué. Veuillez patienter {remaining} secondes.")
        return

    # Si le temps de blocage est écoulé, on remet les compteurs à zéro
    if st.session_state["lockout_time"] > 0 and current_time > st.session_state["lockout_time"]:
        st.session_state["login_attempts"] = 0
        st.session_state["lockout_time"] = 0

    with st.form("login_form"):
        # Autocomplete coupé pour la sécurité
        login = st.text_input("Identifiant (Login)", autocomplete="username")
        password = st.text_input("Mot de passe", type="password", autocomplete="new-password")
        submitted = st.form_submit_button("Se connecter", type="primary", use_container_width=True)

        if submitted:
            if not login or not password:
                st.warning("Veuillez remplir tous les champs.")
            else:
                user_data = authenticate_user(login, password)
                if user_data:
                    # Succès : on réinitialise les compteurs et on met à jour la session
                    st.session_state["login_attempts"] = 0
                    st.session_state["lockout_time"] = 0
                    st.session_state["user"] = user_data
                    st.session_state["authenticated"] = True
                    st.session_state["last_activity"] = time.time() # Utile pour l'expiration
                    st.success(f"Bienvenue, {user_data['nom']} !")
                    st.rerun()
                else:
                    # Échec : On incrémente le compteur
                    st.session_state["login_attempts"] += 1
                    if st.session_state["login_attempts"] >= 3:
                        st.session_state["lockout_time"] = time.time() + 180 # Bloqué 3 minutes
                        st.error("Trop de tentatives échouées. Compte bloqué pour 3 minutes.")
                        st.rerun()
                    else:
                        st.error("Identifiants incorrects ou compte inactif.")

def logout():
    """Déconnecte l'utilisateur et détruit la session."""
    st.session_state["user"] = None
    st.session_state["authenticated"] = False
    st.session_state["last_activity"] = 0
    st.cache_data.clear()
    st.rerun()