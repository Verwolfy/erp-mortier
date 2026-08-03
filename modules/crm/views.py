"""
Interface utilisateur du module CRM.
"""
import streamlit as st
import pandas as pd
from config.roles import has_permission
from core.db_service import fetch_data
from core.listes_service import get_liste, liste_to_dict
from modules.crm.service import create_opportunite, create_interaction, get_pipeline, get_interactions

def get_clients_actifs():
    df = pd.DataFrame(fetch_data("clients"))
    return df[df["actif"] == "OUI"] if not df.empty and "actif" in df.columns else pd.DataFrame()

def show_crm_page():
    st.title("🤝 CRM & Relation Client")

    user_role = st.session_state.get("user", {}).get("role", "")
    can_write = has_permission(user_role, "CRM", "ecriture")

    tab1, tab2, tab3 = st.tabs(["🎯 Pipeline (Opportunités)", "📞 Consigner une interaction", "📋 Historique des échanges"])

    with tab1:
        st.subheader("Gestion du Pipeline")
        if can_write:
            with st.expander("➕ Nouvelle Opportunité"):
                with st.form("form_opp"):
                    c1, c2 = st.columns(2)
                    prospect = c1.text_input("Nom du prospect / entreprise *")
                    contact = c2.text_input("Contact (Nom, Email, Tel)")

                    statut = c1.selectbox("Statut", ["Nouveau", "Contacté", "En Négociation", "Gagné", "Perdu"])
                    commercial = c2.text_input("ID Commercial assigné (ex: USR-0001)")

                    valeur = c1.number_input("Valeur estimée (DZD)", min_value=0.0, step=1000.0)
                    probabilite = c2.slider("Probabilité de succès (%)", 0, 100, 50)

                    if st.form_submit_button("Ajouter au pipeline", type="primary"):
                        if prospect:
                            create_opportunite(prospect, contact, statut, commercial, valeur, float(probabilite))
                            st.success("Opportunité créée !")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error("Le nom du prospect est obligatoire.")

        df_pipe = get_pipeline()
        if not df_pipe.empty:
            st.dataframe(df_pipe, use_container_width=True)
        else:
            st.info("Aucune opportunité en cours.")

    with tab2:
        st.subheader("Consigner une Interaction")
        df_clients = get_clients_actifs()

        if not can_write:
            st.info("🔒 Mode lecture seule.")
        elif df_clients.empty:
            st.warning("Veuillez configurer des clients dans l'Administration.")
        else:
            with st.form("form_interaction"):
                c_cli, c_type = st.columns(2)
                liste_clients = {row["client_id"]: f"{row['client_id']} - {row['nom']}" for _, row in df_clients.iterrows()}
                client_choisi = c_cli.selectbox("Client concerné", options=list(liste_clients.keys()), format_func=lambda x: liste_clients[x])

                # Utilisation du format PascalCase
                dict_types = liste_to_dict(get_liste("TypeInteractionCRM"))
                if not dict_types:
                    dict_types = {"Appel": "Appel", "Email": "Email", "Visite": "Visite", "Relance": "Relance"}
                type_action = c_type.selectbox("Type d'action", options=list(dict_types.keys()), format_func=lambda x: dict_types.get(x, x))

                notes = st.text_area("Notes et compte-rendu")
                date_rappel = st.date_input("Date de prochain rappel (optionnel)", value=None)

                date_rappel_str = str(date_rappel) if date_rappel else ""

                if st.form_submit_button("Enregistrer l'interaction", type="primary"):
                    create_interaction(client_choisi, type_action, notes, date_rappel_str)
                    st.success("Interaction enregistrée !")
                    st.cache_data.clear()
                    st.rerun()

    with tab3:
        st.subheader("Historique des Interactions")
        df_int = get_interactions()
        if not df_int.empty:
            st.dataframe(df_int.sort_values(by="date_creation", ascending=False), use_container_width=True)
        else:
            st.info("Aucun historique disponible.")