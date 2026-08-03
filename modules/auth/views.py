"""
Interface utilisateur pour l'authentification.
"""
import streamlit as st
from modules.auth.service import authenticate_user

def show_login_page():
    """Affiche le formulaire de connexion."""
    st.title("🔐 Connexion ERP")
    st.markdown("Veuillez vous identifier pour accéder au système.")

    with st.form("login_form"):
        login = st.text_input("Identifiant (Login)")
        password = st.text_input("Mot de passe", type="password")
        submitted = st.form_submit_button("Se connecter", type="primary", use_container_width=True)

        if submitted:
            if not login or not password:
                st.warning("Veuillez remplir tous les champs.")
            else:
                user_data = authenticate_user(login, password)
                if user_data:
                    st.session_state["user"] = user_data
                    st.session_state["authenticated"] = True
                    st.success(f"Bienvenue, {user_data['nom']} !")
                    st.rerun()
                else:
                    st.error("Identifiants incorrects ou compte inactif.")

def logout():
    """Déconnecte l'utilisateur."""
    st.session_state["user"] = None
    st.session_state["authenticated"] = False
    st.cache_data.clear()
    st.rerun()