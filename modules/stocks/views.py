"""
Interface utilisateur du module Stocks.
Sépare clairement les Matières Premières (Vrac), les Emballages et les Produits Finis (PF).
"""
import streamlit as st
import pandas as pd
from config.roles import has_permission
from core.db_service import fetch_data
from modules.stocks.service import (
    get_stock_actuel_mp, get_mouvements, enregistrer_entree_mp,
    get_stock_actuel_pf, get_mouvements_pf
)

def get_mp_actives():
    df = pd.DataFrame(fetch_data("matieres_premieres"))
    return df[df["actif"] == "OUI"] if not df.empty and "actif" in df.columns else pd.DataFrame()

def get_skus_actifs():
    df = pd.DataFrame(fetch_data("sku_conditionnement"))
    return df[df["actif"] == "OUI"] if not df.empty and "actif" in df.columns else pd.DataFrame()

def get_produits():
    return pd.DataFrame(fetch_data("produits"))

def show_stocks_page():
    st.title("📦 Gestion des Stocks")

    user_role = st.session_state.get("user", {}).get("role", "")
    can_write = has_permission(user_role, "Stocks", "ecriture")

    tab1, tab2, tab3 = st.tabs(["📊 État des Stocks", "🔄 Entrée Manuelle (Achats)", "📋 Historique des Mouvements"])

    df_mp_global = get_mp_actives()

    # --- ONGLET 1 : ÉTAT DES STOCKS ---
    with tab1:
        st.subheader("Consultation des stocks actuels")

        # Séparation en 3 onglets distincts
        sous_tab_vrac, sous_tab_emb, sous_tab_pf = st.tabs(["🧪 Matières Premières (Vrac)", "📦 Emballages", "🛍️ Produits Finis"])

        df_stock = get_stock_actuel_mp()

        if not df_stock.empty and not df_mp_global.empty:
            df_display = pd.merge(df_stock, df_mp_global[['mp_id', 'nom', 'unite_stock', 'stock_mini', 'categorie_mp']], on='mp_id', how='left')
            df_vrac = df_display[df_display["categorie_mp"] != "EMBALLAGE_CONSOMMABLE"]
            df_emb = df_display[df_display["categorie_mp"] == "EMBALLAGE_CONSOMMABLE"]
        else:
            df_vrac = pd.DataFrame()
            df_emb = pd.DataFrame()

        with sous_tab_vrac:
            if not df_vrac.empty:
                st.dataframe(
                    df_vrac[["mp_id", "nom", "quantite_disponible", "unite_stock", "cmp_actuel", "stock_mini", "derniere_maj"]],
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("Aucun stock actuel disponible pour les Matières Premières (Vrac).")

        with sous_tab_emb:
            if not df_emb.empty:
                st.dataframe(
                    df_emb[["mp_id", "nom", "quantite_disponible", "unite_stock", "cmp_actuel", "stock_mini", "derniere_maj"]],
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("Aucun stock actuel disponible pour les Emballages.")

        with sous_tab_pf:
            df_stock_pf = get_stock_actuel_pf()
            df_skus = get_skus_actifs()
            df_prods = get_produits()

            if not df_stock_pf.empty and not df_skus.empty and not df_prods.empty:
                df_skus_prods = pd.merge(df_skus, df_prods[['pf_id', 'nom']], on='pf_id', how='left')
                df_skus_prods['nom_complet'] = df_skus_prods['nom'] + " - " + df_skus_prods['format'].fillna("")

                df_display_pf = pd.merge(df_stock_pf, df_skus_prods[['sku_id', 'nom_complet', 'unite_vente']], on='sku_id', how='left')

                st.dataframe(
                    df_display_pf[["sku_id", "nom_complet", "quantite_disponible", "unite_vente", "cout_revient", "derniere_maj"]],
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("Aucun stock de Produits Finis n'a encore été généré par la Production.")

    # --- ONGLET 2 : ENTRÉE MANUELLE ---
    with tab2:
        st.subheader("Ajustement / Entrée manuelle")
        st.info("Les entrées de Produits Finis se font uniquement via le module de Production (Clôture d'OF).")

        if not can_write:
            st.warning("🔒 Mode lecture seule : vous n'avez pas les droits de modification des stocks.")
        elif not df_mp_global.empty:
            # Sélecteur pour faciliter la recherche du magasinier
            type_entree = st.radio("Que souhaitez-vous approvisionner ?", ["🧪 Matière Première (Vrac)", "📦 Emballage"], horizontal=True)

            if "Emballage" in type_entree:
                df_mp_filtre = df_mp_global[df_mp_global["categorie_mp"] == "EMBALLAGE_CONSOMMABLE"]
            else:
                df_mp_filtre = df_mp_global[df_mp_global["categorie_mp"] != "EMBALLAGE_CONSOMMABLE"]

            if df_mp_filtre.empty:
                st.warning(f"Aucun article de type '{type_entree}' n'a été trouvé dans le référentiel.")
            else:
                with st.form("form_entree_stock"):
                    c1, c2 = st.columns(2)
                    liste_mp = {row["mp_id"]: f"{row['mp_id']} - {row['nom']}" for _, row in df_mp_filtre.iterrows()}
                    mp_choisie = c1.selectbox("Article sélectionné", options=list(liste_mp.keys()), format_func=lambda x: liste_mp[x])

                    quantite = c2.number_input("Quantité réceptionnée", min_value=0.1, step=1.0)
                    prix_entree = c1.number_input("Prix d'entrée unitaire (DZD)", min_value=0.0, step=10.0)
                    reference = c2.text_input("Référence (ex: BL Fournisseur, Ajustement)")
                    date_peremption = c1.date_input("Date de péremption")

                    if st.form_submit_button("Valider l'entrée en stock", type="primary"):
                        if reference:
                            enregistrer_entree_mp(mp_choisie, quantite, prix_entree, reference, str(date_peremption))
                            st.success(f"Stock mis à jour pour {liste_mp[mp_choisie]}.")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error("Veuillez saisir une référence.")
        else:
            st.warning("Aucun article actif trouvé dans le référentiel.")

    # --- ONGLET 3 : HISTORIQUE DES MOUVEMENTS ---
    with tab3:
        st.subheader("Historique des mouvements")

        sous_tab_hist_vrac, sous_tab_hist_emb, sous_tab_hist_pf = st.tabs(["🧪 Mouvements Vrac", "📦 Mouvements Emballages", "🛍️ Mouvements PF"])

        df_mouv = get_mouvements()
        if not df_mouv.empty and not df_mp_global.empty:
            df_mouv_detail = pd.merge(df_mouv, df_mp_global[['mp_id', 'categorie_mp']], on='mp_id', how='left')
            df_mouv_vrac = df_mouv_detail[df_mouv_detail["categorie_mp"] != "EMBALLAGE_CONSOMMABLE"]
            df_mouv_emb = df_mouv_detail[df_mouv_detail["categorie_mp"] == "EMBALLAGE_CONSOMMABLE"]
        else:
            df_mouv_vrac = pd.DataFrame()
            df_mouv_emb = pd.DataFrame()

        with sous_tab_hist_vrac:
            if not df_mouv_vrac.empty:
                st.dataframe(df_mouv_vrac.drop(columns=["categorie_mp"]).sort_values(by="date", ascending=False), use_container_width=True, hide_index=True)
            else:
                st.info("Aucun mouvement enregistré pour le Vrac.")

        with sous_tab_hist_emb:
            if not df_mouv_emb.empty:
                st.dataframe(df_mouv_emb.drop(columns=["categorie_mp"]).sort_values(by="date", ascending=False), use_container_width=True, hide_index=True)
            else:
                st.info("Aucun mouvement enregistré pour les Emballages.")

        with sous_tab_hist_pf:
            df_mouv_pf = get_mouvements_pf()
            if not df_mouv_pf.empty:
                st.dataframe(df_mouv_pf.sort_values(by="date", ascending=False), use_container_width=True, hide_index=True)
            else:
                st.info("Aucun mouvement enregistré pour les Produits Finis.")