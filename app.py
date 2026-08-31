"""
Point d'entrée principal de l'application ERP.
Gère le routage, l'authentification (avec Timeout de session) et le menu latéral.
"""
import time
import streamlit as st

# Configuration de la page (doit être le premier appel Streamlit)
st.set_page_config(
    page_title="ERP Mortier & Adjuvants",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

from modules.auth.views import show_login_page, logout
from config.roles import get_allowed_modules

TIMEOUT_SECONDS = 1800  # 30 minutes d'inactivité maximum

def main():
    # Initialisation de l'état de session
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    if "user" not in st.session_state:
        st.session_state["user"] = None
    if "last_activity" not in st.session_state:
        st.session_state["last_activity"] = time.time()

    # --- VÉRIFICATION DU TIMEOUT D'INACTIVITÉ ---
    if st.session_state["authenticated"]:
        current_time = time.time()
        if current_time - st.session_state["last_activity"] > TIMEOUT_SECONDS:
            st.warning("Votre session a expiré pour cause d'inactivité. Veuillez vous reconnecter.")
            logout()
            return
        else:
            # L'utilisateur navigue, on met à jour son horloge d'activité
            st.session_state["last_activity"] = current_time

    # Si non authentifié, on force la page de connexion
    if not st.session_state["authenticated"]:
        show_login_page()
        return

    # --- UTILISATEUR CONNECTÉ ---
    user = st.session_state["user"]
    user_role = user.get("role", "")

    # Récupération dynamique des droits depuis ERP_Referentiels > Permissions
    allowed_modules = get_allowed_modules(user_role)

    # --- MENU LATÉRAL ---
    with st.sidebar:
        st.write(f"👤 **{user.get('nom', 'Utilisateur')}**")
        st.caption(f"Rôle : {user_role}")
        if st.button("🚪 Déconnexion", use_container_width=True):
            logout()

        st.divider()
        st.subheader("Navigation")

        # Dictionnaire des modules disponibles (icône + nom d'affichage)
        menu_options = {}
        if "Administration" in allowed_modules:
            menu_options["Administration"] = "⚙️ Administration"
            menu_options["Securite"] = "🔐 Utilisateurs & Sécurité"

        if "Achats" in allowed_modules:
            menu_options["Achats"] = "🛒 Achats & Appro."
        if "Stocks" in allowed_modules:
            menu_options["Stocks"] = "📦 Stocks"
        if "Production" in allowed_modules:
            menu_options["Production"] = "🏭 Production"
        if "Ventes" in allowed_modules:
            menu_options["Ventes"] = "🧾 Ventes & Facturation"
        if "CRM" in allowed_modules:
            menu_options["CRM"] = "🤝 CRM"
        if "Finance" in allowed_modules:
            menu_options["Finance"] = "🏦 Comptabilité & Finances"
        if "RH" in allowed_modules:
            menu_options["RH"] = "👥 Ressources Humaines"
        if "Dashboards" in allowed_modules:
            menu_options["Dashboards"] = "📊 Tableaux de bord"

        # Le module d'aide est ajouté systématiquement pour tous les utilisateurs
        menu_options["Help"] = "📚 Guide & Aide"

        # Sélecteur de navigation
        if menu_options:
            choix_menu = st.radio("Aller vers :", list(menu_options.keys()), format_func=lambda x: menu_options[x])
        else:
            st.warning("Aucun module assigné.")
            choix_menu = None

    # --- ROUTAGE VERS LES MODULES ---
    if choix_menu == "Administration":
        from modules.admin.views import show_admin_page
        show_admin_page()
    elif choix_menu == "Securite":
        from modules.admin.views import show_user_management
        show_user_management()
    elif choix_menu == "Achats":
        from modules.achats.views import show_achats_page
        show_achats_page()
    elif choix_menu == "Stocks":
        from modules.stocks.views import show_stocks_page
        show_stocks_page()
    elif choix_menu == "Production":
        from modules.production.views import show_production_page
        show_production_page()
    elif choix_menu == "Ventes":
        from modules.ventes.views import show_ventes_page
        show_ventes_page()
    elif choix_menu == "CRM":
        from modules.crm.views import show_crm_page
        show_crm_page()
    elif choix_menu == "Finance":
        from modules.finance.views import show_finance_page
        show_finance_page()
    elif choix_menu == "RH":
        from modules.rh.views import show_rh_page
        show_rh_page()
    elif choix_menu == "Dashboards":
        from modules.dashboards.views import show_dashboards_page
        show_dashboards_page()
    elif choix_menu == "Help":
        from modules.help.views import show_help_page
        show_help_page()

if __name__ == "__main__":
    main()