"""
Interface utilisateur du module Stocks.
"""
import streamlit as st
import pandas as pd
from config.roles import has_permission
from core.db_service import fetch_data
from modules.stocks.service import get_stock_actuel_mp, get_mouvements, enregistrer_entree_mp

def get_mp_actives():
    df = pd.DataFrame(fetch_data("matieres_premieres"))
    return df[df["actif"] == "OUI"] if not df.empty and "actif" in df.columns else pd.DataFrame()

def show_stocks_page():
    st.title("📦 Gestion des Stocks")

    user_role = st.session_state.get("user", {}).get("role", "")
    can_write = has_permission(user_role, "Stocks", "ecriture")

    tab1, tab2, tab3 = st.tabs(["📊 Stock Actuel (MP)", "🔄 Entrée Manuelle", "📋 Historique des Mouvements"])

    with tab1:
        st.subheader("État du stock des Matières Premières")
        df_stock = get_stock_actuel_mp()
        df_mp = get_mp_actives()

        if not df_stock.empty and not df_mp.empty:
            # Fusion avec le référentiel pour afficher le nom de l'article
            df_display = pd.merge(df_stock, df_mp[['mp_id', 'nom', 'unite_stock', 'stock_mini']], on='mp_id', how='left')

            # Mise en évidence des ruptures de stock
            st.dataframe(
                df_display[["mp_id", "nom", "quantite_disponible", "unite_stock", "cmp_actuel", "stock_mini", "derniere_maj"]],
                use_container_width=True
            )
        else:
            st.info("Aucun stock actuel disponible.")

    with tab2:
        st.subheader("Ajustement / Entrée manuelle")
        if not can_write:
            st.info("🔒 Mode lecture seule : vous n'avez pas les droits de modification des stocks.")
        else:
            if not df_mp.empty:
                with st.form("form_entree_stock"):
                    c1, c2 = st.columns(2)
                    liste_mp = {row["mp_id"]: f"{row['mp_id']} - {row['nom']}" for _, row in df_mp.iterrows()}
                    mp_choisie = c1.selectbox("Matière Première", options=list(liste_mp.keys()), format_func=lambda x: liste_mp[x])

                    quantite = c2.number_input("Quantité", min_value=0.1, step=1.0)
                    prix_entree = c1.number_input("Prix d'entrée unitaire (DZD)", min_value=0.0, step=10.0)
                    reference = c2.text_input("Référence (ex: BL Fournisseur, Ajustement)")
                    date_peremption = c1.date_input("Date de péremption")

                    if st.form_submit_button("Valider l'entrée en stock", type="primary"):
                        if reference:
                            enregistrer_entree_mp(mp_choisie, quantite, prix_entree, reference, str(date_peremption))
                            st.success(f"Stock mis à jour pour {liste_mp[mp_choisie]}.")
                            st.rerun()
                        else:
                            st.error("Veuillez saisir une référence.")
            else:
                st.warning("Aucune matière première active trouvée dans le référentiel.")

    with tab3:
        st.subheader("Historique des mouvements")
        df_mouv = get_mouvements()
        if not df_mouv.empty:
            st.dataframe(
                df_mouv.sort_values(by="date", ascending=False),
                use_container_width=True
            )
        else:
            st.info("Aucun mouvement enregistré.")