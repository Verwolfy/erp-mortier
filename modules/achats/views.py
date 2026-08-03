"""
Interface utilisateur pour le module Achats (Commandes Fournisseurs).
"""
import streamlit as st
import pandas as pd
from config.roles import has_permission
from core.listes_service import get_liste, liste_to_dict
from core.db_service import fetch_data
from modules.achats.service import create_commande_achat, get_commandes

def get_fournisseurs_actifs():
    df = pd.DataFrame(fetch_data("fournisseurs"))
    return df[df["actif"] == "OUI"] if not df.empty and "actif" in df.columns else pd.DataFrame()

def get_mp_actives():
    df = pd.DataFrame(fetch_data("matieres_premieres"))
    return df[df["actif"] == "OUI"] if not df.empty and "actif" in df.columns else pd.DataFrame()

def show_achats_page():
    st.title("🛒 Achats & Approvisionnements")

    user_role = st.session_state.get("user", {}).get("role", "")
    can_write = has_permission(user_role, "Achats", "ecriture")

    if "panier_achats" not in st.session_state:
        st.session_state["panier_achats"] = []

    tab1, tab2 = st.tabs(["➕ Nouvelle Commande", "📋 Historique des Commandes"])

    with tab1:
        if not can_write:
            st.info("🔒 Accès en lecture seule. Création de commande désactivée.")
        else:
            df_fournisseurs = get_fournisseurs_actifs()
            df_mp = get_mp_actives()

            if df_fournisseurs.empty or df_mp.empty:
                st.warning("Veuillez d'abord configurer des Fournisseurs et Matières Premières actifs dans l'Administration.")
            else:
                # --- EN-TÊTE ---
                st.subheader("1. Informations Fournisseur")
                col1, col2 = st.columns(2)
                liste_fournisseurs = {row["fournisseur_id"]: f"{row['fournisseur_id']} - {row['nom']}" for _, row in df_fournisseurs.iterrows()}
                fournisseur_id = col1.selectbox("Fournisseur", options=list(liste_fournisseurs.keys()), format_func=lambda x: liste_fournisseurs[x])

                type_achat = col2.selectbox("Type d'achat", ["Matière Première", "Emballage", "Frais Généraux"])

                col3, col4, col5 = st.columns(3)

                # Devise
                dict_devise = liste_to_dict(get_liste("Devise"))
                if not dict_devise:
                    dict_devise = {"DZD": "DZD", "EUR": "EUR", "USD": "USD"}
                devise = col3.selectbox("Devise", options=list(dict_devise.keys()), format_func=lambda x: dict_devise.get(x, x))

                taux_change = col4.number_input("Taux de change (1 si DZD)", min_value=1.0, value=1.0, step=0.1)
                date_voulue = col5.date_input("Date de livraison souhaitée")

                st.divider()

                # --- PANIER (LIGNES D'ACHATS) ---
                st.subheader("2. Lignes de Commande")
                with st.expander("➕ Ajouter un article", expanded=True):
                    c_mp, c_qte, c_prix, c_btn = st.columns([3, 1, 1, 1])
                    liste_mp = {row["mp_id"]: f"{row['mp_id']} - {row['nom']}" for _, row in df_mp.iterrows()}
                    mp_choisie = c_mp.selectbox("Article", options=list(liste_mp.keys()), format_func=lambda x: liste_mp[x])

                    qte = c_qte.number_input("Quantité", min_value=1.0, step=1.0)
                    prix_u = c_prix.number_input(f"Prix Unitaire ({devise})", min_value=0.0, step=1.0)

                    if c_btn.button("Ajouter", use_container_width=True):
                        st.session_state["panier_achats"].append({
                            "mp_id": mp_choisie,
                            "nom_article": liste_mp[mp_choisie],
                            "unite_cond": "Unité",
                            "qte_cond": qte,
                            "qte_totale": qte,
                            "prix_unitaire": prix_u,
                            "total_devise": qte * prix_u
                        })
                        st.rerun()

                if st.session_state["panier_achats"]:
                    df_panier = pd.DataFrame(st.session_state["panier_achats"])
                    st.dataframe(df_panier[["mp_id", "nom_article", "qte_totale", "prix_unitaire", "total_devise"]], use_container_width=True)

                    if st.button("🗑️ Vider"):
                        st.session_state["panier_achats"] = []
                        st.rerun()
                else:
                    st.info("Aucun article dans la commande.")

                st.divider()

                # --- VALIDATION ---
                st.subheader("3. Modalités & Validation")
                c_mode, c_delai, c_valider = st.columns(3)

                # Mode de paiement
                dict_mode = liste_to_dict(get_liste("ModePaiement"))
                if not dict_mode:
                    dict_mode = {"Virement": "Virement", "Chèque": "Chèque", "Espèces": "Espèces"}
                mode_paiement = c_mode.selectbox("Mode de paiement", options=list(dict_mode.keys()), format_func=lambda x: dict_mode.get(x, x))

                # Délai de paiement
                dict_delai = liste_to_dict(get_liste("ConditionPaiement"))
                if not dict_delai:
                    dict_delai = {"Comptant": "Comptant", "30 jours": "30 jours", "60 jours": "60 jours"}
                delai_paiement = c_delai.selectbox("Délai de paiement", options=list(dict_delai.keys()), format_func=lambda x: dict_delai.get(x, x))

                if c_valider.button("✅ Générer la commande", type="primary", use_container_width=True, disabled=len(st.session_state["panier_achats"])==0):
                    cmd_id = create_commande_achat(
                        fournisseur_id=fournisseur_id, type_achat=type_achat, devise=devise,
                        taux_change=taux_change, mode_paiement=mode_paiement,
                        delai_paiement=delai_paiement, date_voulue=str(date_voulue),
                        panier=st.session_state["panier_achats"]
                    )
                    st.session_state["panier_achats"] = []
                    st.success(f"Commande {cmd_id} validée !")
                    st.cache_data.clear()
                    st.rerun()

    with tab2:
        st.subheader("Suivi des Commandes")
        df_commandes = get_commandes()
        if not df_commandes.empty:
            st.dataframe(df_commandes, use_container_width=True)
        else:
            st.info("Aucune commande enregistrée pour le moment.")