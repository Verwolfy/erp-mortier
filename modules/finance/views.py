"""
Interface utilisateur du module Comptabilité & Finances.
Saisie des flux et affectation (lettrage) sur factures.
"""
import streamlit as st
import pandas as pd
from core.db_service import fetch_data
from core.listes_service import get_liste, liste_to_dict
from modules.finance.service import (
    get_comptes, creer_compte, get_reglements,
    enregistrer_reglement, enregistrer_lettrage
)

def show_finance_page():
    st.title("🏦 Comptabilité & Trésorerie")

    tab_bord, tab_comptes, tab_reglements, tab_lettrage = st.tabs([
        "📊 Tableau de bord",
        "🏦 Comptes & Caisses",
        "💸 Saisie Règlements",
        "🔗 Lettrage (Affectation)"
    ])

    df_comptes = get_comptes()
    df_reg = get_reglements()

    # Référentiels
    df_clients = pd.DataFrame(fetch_data("clients"))

    dict_modes = liste_to_dict(get_liste("ModePaiement"))
    liste_modes = list(dict_modes.keys()) if dict_modes else ["ESPECES", "CHEQUE", "VIREMENT"]

    with tab_bord:
        st.subheader("Vue d'ensemble de la trésorerie")
        if df_reg.empty:
            st.info("Aucun mouvement enregistré pour le moment.")
        else:
            encaissements = df_reg[df_reg["type_flux"] == "ENCAISSEMENT"]["montant_total"].astype(float).sum()
            decaissements = df_reg[df_reg["type_flux"] == "DECAISSEMENT"]["montant_total"].astype(float).sum()

            c1, c2, c3 = st.columns(3)
            c1.metric("Total Encaissements", f"{encaissements:,.2f} DZD")
            c2.metric("Total Décaissements", f"{decaissements:,.2f} DZD", delta_color="inverse")
            c3.metric("Solde Net Période", f"{(encaissements - decaissements):,.2f} DZD")

            st.dataframe(df_reg.sort_values(by="date_reglement", ascending=False), use_container_width=True)

    with tab_comptes:
        st.subheader("Gestion des Comptes Financiers")
        with st.expander("➕ Créer un nouveau compte / caisse"):
            c1, c2 = st.columns(2)
            nom = c1.text_input("Nom du compte (ex: Caisse Principale, BNA)")
            type_c = c2.selectbox("Type", ["Caisse", "Banque"])
            num = c1.text_input("Numéro de compte / RIB (Optionnel)")
            solde = c2.number_input("Solde initial (DZD)", min_value=0.0, step=1000.0)

            if st.button("Enregistrer le compte", type="primary"):
                if nom:
                    creer_compte(nom, type_c, num, solde)
                    st.success(f"Compte '{nom}' créé avec succès !")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("Le nom du compte est obligatoire.")

        if not df_comptes.empty:
            st.dataframe(df_comptes, use_container_width=True, hide_index=True)
        else:
            st.warning("Aucun compte configuré pour le moment.")

    with tab_reglements:
        st.subheader("Enregistrement des Flux (Entrées / Sorties)")

        if df_comptes.empty:
            st.warning("Veuillez d'abord créer au moins un Compte/Caisse dans l'onglet précédent.")
        else:
            with st.form("form_saisie_reglement"):
                c_type, c_date = st.columns(2)
                type_flux = c_type.radio("Type d'opération", ["ENCAISSEMENT", "DECAISSEMENT"])
                date_reg = c_date.date_input("Date de l'opération")

                c_part, c_cpt = st.columns(2)
                # Affichage des clients (Simplifié pour encaissements)
                dict_clients = {row["client_id"]: f"{row['nom']} ({row['client_id']})" for _, row in df_clients.iterrows()} if not df_clients.empty else {}
                partenaire_id = c_part.selectbox("Partenaire (Client / Fournisseur)", options=list(dict_clients.keys()), format_func=lambda x: dict_clients[x])

                dict_comptes = {row["compte_id"]: f"{row['nom_compte']} ({row['type_compte']})" for _, row in df_comptes.iterrows()}
                compte_id = c_cpt.selectbox("Compte de trésorerie impacté", options=list(dict_comptes.keys()), format_func=lambda x: dict_comptes[x])

                c_mode, c_ref, c_mont = st.columns(3)
                mode_paiement = c_mode.selectbox("Mode de paiement", liste_modes)
                reference = c_ref.text_input("Référence (N° Chèque, Tracabilité)")
                montant = c_mont.number_input("Montant total (DZD)", min_value=1.0, step=100.0)

                if st.form_submit_button("Enregistrer le flux", type="primary"):
                    if partenaire_id and compte_id:
                        reg_id = enregistrer_reglement(str(date_reg), type_flux, partenaire_id, compte_id, mode_paiement, reference, montant)
                        st.success(f"Règlement {reg_id} enregistré avec succès.")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error("Veuillez sélectionner un partenaire et un compte.")

    with tab_lettrage:
        st.subheader("Lettrage des Factures (Affectation des Règlements)")

        if df_reg.empty:
            st.info("Aucun règlement disponible pour le lettrage.")
        else:
            # Règlements avec solde non alloué > 0
            df_reg["montant_total"] = pd.to_numeric(df_reg["montant_total"], errors="coerce").fillna(0)
            df_reg["montant_alloue"] = pd.to_numeric(df_reg["montant_alloue"], errors="coerce").fillna(0)
            df_reg_ouverts = df_reg[df_reg["montant_total"] > df_reg["montant_alloue"]]

            # Factures clients non soldées
            df_fac = pd.DataFrame(fetch_data("factures"))
            if df_fac.empty:
                st.warning("Aucune facture existante dans le système.")
            else:
                df_fac["montant_ttc"] = pd.to_numeric(df_fac["montant_ttc"], errors="coerce").fillna(0)
                df_fac["montant_paye"] = pd.to_numeric(df_fac["montant_paye"], errors="coerce").fillna(0)
                df_fac_ouvertes = df_fac[df_fac["montant_ttc"] > df_fac["montant_paye"]]

                if df_reg_ouverts.empty:
                    st.success("Tous les règlements ont été entièrement affectés (lettrés).")
                elif df_fac_ouvertes.empty:
                    st.success("Toutes les factures ont été payées.")
                else:
                    with st.form("form_lettrage"):
                        c1, c2 = st.columns(2)

                        dict_regs = {}
                        for _, r in df_reg_ouverts.iterrows():
                            reste = r['montant_total'] - r['montant_alloue']
                            dict_regs[r['reglement_id']] = f"{r['reglement_id']} | Reste: {reste:,.2f} DZD (Client: {r['partenaire_id']})"

                        dict_facs = {}
                        for _, f in df_fac_ouvertes.iterrows():
                            reste = f['montant_ttc'] - f['montant_paye']
                            dict_facs[f['facture_id']] = f"{f['facture_id']} | À Payer: {reste:,.2f} DZD (Client: {f['client_id']})"

                        reg_choisi = c1.selectbox("1. Sélectionner un règlement en attente", options=list(dict_regs.keys()), format_func=lambda x: dict_regs[x])
                        fac_choisie = c2.selectbox("2. Sélectionner une facture à solder", options=list(dict_facs.keys()), format_func=lambda x: dict_facs[x])

                        montant_appliquer = st.number_input("3. Montant à imputer sur cette facture (DZD)", min_value=1.0, step=100.0)

                        if st.form_submit_button("Lier le règlement à la facture (Lettrer)", type="primary"):
                            try:
                                enregistrer_lettrage(reg_choisi, fac_choisie, "FactureClient", montant_appliquer)
                                st.success("Lettrage effectué ! La facture et le règlement ont été mis à jour.")
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erreur de lettrage : {e}")