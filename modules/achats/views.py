"""
Interface utilisateur pour le module Achats (Commandes Fournisseurs & Réceptions).
"""
import streamlit as st
import pandas as pd
from config.roles import has_permission
from core.listes_service import get_liste, liste_to_dict
from core.db_service import fetch_data
from modules.achats.service import (
    create_commande_achat, get_commandes, get_lignes_achats,
    creer_bon_reception, get_bons_reception
)
from core.utils import get_local_now

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

    tab1, tab2, tab3 = st.tabs(["➕ Nouvelle Commande", "📦 Réception & Entrée Stock", "📋 Historique & Suivi"])

    # --- TAB 1 : NOUVELLE COMMANDE ---
    with tab1:
        if not can_write:
            st.info("🔒 Accès en lecture seule. Création de commande désactivée.")
        else:
            df_fournisseurs = get_fournisseurs_actifs()
            df_mp = get_mp_actives()

            if df_fournisseurs.empty or df_mp.empty:
                st.warning("Veuillez d'abord configurer des Fournisseurs et Matières Premières actifs dans l'Administration.")
            else:
                st.subheader("1. Informations Fournisseur")
                col1, col2 = st.columns(2)
                liste_fournisseurs = {row["fournisseur_id"]: f"{row['fournisseur_id']} - {row['nom']}" for _, row in df_fournisseurs.iterrows()}
                fournisseur_id = col1.selectbox("Fournisseur", options=list(liste_fournisseurs.keys()), format_func=lambda x: liste_fournisseurs[x])

                type_achat = col2.selectbox("Type d'achat", ["Matière Première", "Emballage", "Frais Généraux"])

                col3, col4, col5 = st.columns(3)

                dict_devise = liste_to_dict(get_liste("Devise"))
                if not dict_devise:
                    dict_devise = {"DZD": "DZD", "EUR": "EUR", "USD": "USD"}
                devise = col3.selectbox("Devise", options=list(dict_devise.keys()), format_func=lambda x: dict_devise.get(x, x))

                taux_change = col4.number_input("Taux de change (1 si DZD)", min_value=1.0, value=1.0, step=0.1)
                date_voulue = col5.date_input("Date de livraison souhaitée")

                st.divider()

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

                st.subheader("3. Modalités & Validation")
                c_mode, c_delai, c_valider = st.columns(3)

                dict_mode = liste_to_dict(get_liste("ModePaiement"))
                if not dict_mode:
                    dict_mode = {"Virement": "Virement", "Chèque": "Chèque", "Espèces": "Espèces"}
                mode_paiement = c_mode.selectbox("Mode de paiement", options=list(dict_mode.keys()), format_func=lambda x: dict_mode.get(x, x))

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
                    st.success(f"Commande {cmd_id} enregistrée avec succès !")
                    st.cache_data.clear()
                    st.rerun()

    # --- TAB 2 : RÉCEPTION & ENTRÉE STOCK ---
    with tab2:
        st.subheader("Générer un Bon de Réception (BR)")
        df_commandes = get_commandes()

        if not can_write:
            st.info("🔒 Mode lecture seule.")
        elif df_commandes.empty:
            st.info("Aucune commande enregistrée.")
        else:
            df_en_attente = df_commandes[df_commandes["statut"] == "EN_ATTENTE"]
            if df_en_attente.empty:
                st.success("Toutes les commandes d'achats ont été réceptionnées !")
            else:
                liste_cmds = {row["commande_achat_id"]: f"{row['commande_achat_id']} - Fournisseur: {row['fournisseur_id']} ({row['date_commande']})" for _, row in df_en_attente.iterrows()}
                cmd_choisie = st.selectbox("Sélectionnez la commande à réceptionner", options=list(liste_cmds.keys()), format_func=lambda x: liste_cmds[x])

                if cmd_choisie:
                    df_lignes = get_lignes_achats(cmd_choisie)
                    st.markdown("**Contenu de la commande :**")

                    items_recus = []
                    with st.form("form_reception"):
                        c1, c2 = st.columns(2)
                        date_rec = c1.date_input("Date de réception", value=get_local_now())
                        conformite = c2.radio("Contrôle de conformité", ["CONFORME", "RESERVE", "NON_CONFORME"], horizontal=True)

                        c3, c4 = st.columns(2)
                        remarques = c3.text_input("Remarques / Observation")
                        date_peremp = c4.date_input("Date de péremption des produits")

                        st.divider()
                        st.markdown("**Quantités réceptionnées :**")

                        for idx, row in df_lignes.iterrows():
                            mp_id = row["mp_id"]
                            qte_commandee = float(row["qte_totale"])
                            prix_u = float(row.get("prix_unitaire", 0.0))

                            qte_r = st.number_input(
                                f"Article {mp_id} (Commandé : {qte_commandee})",
                                min_value=0.0,
                                value=qte_commandee,
                                step=1.0,
                                key=f"rec_{idx}"
                            )
                            items_recus.append({
                                "mp_id": mp_id,
                                "quantite_recue": qte_r,
                                "prix_unitaire": prix_u
                            })

                        if st.form_submit_button("📦 Valider la réception & Alimenter les stocks", type="primary"):
                            try:
                                br_id = creer_bon_reception(
                                    commande_achat_id=cmd_choisie,
                                    date_reception=str(date_rec),
                                    controle_conformite=conformite,
                                    remarques=remarques,
                                    items_recus=items_recus,
                                    date_peremption=str(date_peremp)
                                )
                                st.success(f"✅ Bon de Réception {br_id} généré ! Les stocks ont été automatiquement mis à jour.")
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Erreur lors de la réception : {e}")

    # --- TAB 3 : HISTORIQUE ET SUIVI ---
    with tab3:
        st.subheader("Commandes d'Achats")
        df_commandes = get_commandes()
        if not df_commandes.empty:
            st.dataframe(df_commandes.sort_values(by="date_commande", ascending=False), use_container_width=True, hide_index=True)
        else:
            st.info("Aucune commande enregistrée.")

        st.divider()
        st.subheader("Bons de Réception (BR)")
        df_br = get_bons_reception()
        if not df_br.empty:
            st.dataframe(df_br.sort_values(by="date_reception", ascending=False), use_container_width=True, hide_index=True)
        else:
            st.info("Aucun bon de réception généré pour le moment.")