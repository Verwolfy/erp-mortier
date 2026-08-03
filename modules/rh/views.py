"""
Interface utilisateur du module RH.
"""
import streamlit as st
import pandas as pd
from config.roles import has_permission
from modules.rh.service import create_employe, create_demande_conge, get_employes, get_conges


def show_rh_page():
    st.title("👥 Ressources Humaines")

    user_role = st.session_state.get("user", {}).get("role", "")
    can_write = has_permission(user_role, "RH", "ecriture")

    tab1, tab2 = st.tabs(["👨‍💼 Registre des Employés", "🌴 Gestion des Congés"])

    with tab1:
        st.subheader("Employés")
        if can_write:
            with st.expander("➕ Ajouter un employé"):
                with st.form("form_employe"):
                    c1, c2 = st.columns(2)
                    nom = c1.text_input("Nom complet *")
                    poste = c2.text_input("Poste")
                    service = c1.selectbox("Service",
                                           ["Direction", "Production", "Ventes", "Logistique", "RH", "Maintenance"])
                    manager = c2.text_input("ID Manager (Optionnel)")
                    date_embauche = c1.date_input("Date d'embauche")

                    if st.form_submit_button("Enregistrer", type="primary"):
                        if nom:
                            create_employe(nom, poste, service, manager, str(date_embauche))
                            st.success(f"Employé {nom} ajouté avec succès !")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error("Le nom est obligatoire.")

        df_emp = get_employes()
        if not df_emp.empty:
            st.dataframe(df_emp, use_container_width=True)
        else:
            st.info("Aucun employé enregistré.")

    with tab2:
        st.subheader("Demandes de Congés")
        if can_write:
            if df_emp.empty:
                st.warning("Veuillez d'abord ajouter des employés pour saisir des congés.")
            else:
                with st.form("form_conges"):
                    c_emp, c_dates = st.columns(2)
                    liste_employes = {row["employe_id"]: f"{row['employe_id']} - {row['nom']}" for _, row in
                                      df_emp.iterrows() if str(row.get("actif", "")) == "OUI"}
                    emp_choisi = c_emp.selectbox("Employé", options=list(liste_employes.keys()),
                                                 format_func=lambda x: liste_employes[x])

                    c_deb, c_fin = c_dates.columns(2)
                    date_debut = c_deb.date_input("Date de début")
                    date_fin = c_fin.date_input("Date de fin")
                    motif = st.text_input("Motif (Ex: Congé annuel, Maladie)")

                    if st.form_submit_button("Soumettre la demande", type="primary"):
                        if date_fin < date_debut:
                            st.error("La date de fin ne peut pas précéder la date de début.")
                        else:
                            create_demande_conge(emp_choisi, str(date_debut), str(date_fin), motif)
                            st.success("Demande enregistrée !")
                            st.cache_data.clear()
                            st.rerun()

        df_conges = get_conges()
        if not df_conges.empty:
            st.dataframe(df_conges, use_container_width=True)
        else:
            st.info("Aucune demande de congé.")