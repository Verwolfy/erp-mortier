"""
Interface utilisateur du module Comptabilité & Finances.
Saisie des flux, lettrage sur factures clients/fournisseurs et consultation du Grand Livre.
"""
import streamlit as st
import pandas as pd
from config.roles import has_permission
from core.db_service import fetch_data
from core.listes_service import get_liste, liste_to_dict
from modules.finance.service import (
    get_comptes, creer_compte, get_reglements,
    enregistrer_reglement, enregistrer_lettrage,
    get_ecritures_comptables
)

def show_finance_page():
    st.title("🏦 Comptabilité & Trésorerie")

    user_role = st.session_state.get("user", {}).get("role", "")
    can_write = has_permission(user_role, "Finance", "ecriture")

    tab_bord, tab_comptes, tab_reglements, tab_lettrage, tab_livre = st.tabs([
        "📊 Tableau de bord",
        "🏦 Comptes & Caisses",
        "💸 Saisie Règlements",
        "🔗 Lettrage (Affectation)",
        "📖 Grand Livre"
    ])

    df_comptes = get_comptes()
    df_reg = get_reglements()
    df_clients = pd.DataFrame(fetch_data("clients"))
    df_fournisseurs = pd.DataFrame(fetch_data("fournisseurs"))

    dict_modes = liste_to_dict(get_liste("ModePaiement"))
    liste_modes = list(dict_modes.keys()) if dict_modes else ["ESPECES", "CHEQUE", "VIREMENT"]

    # --- TAB 1 : TABLEAU DE BORD ---
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

            st.dataframe(df_reg.sort_values(by="date_reglement", ascending=False), use_container_width=True, hide_index=True)

    # --- TAB 2 : COMPTES ET CAISSES ---
    with tab_comptes:
        st.subheader("Gestion des Comptes Financiers")
        if not can_write:
            st.info("🔒 Mode lecture seule.")
        else:
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

    # --- TAB 3 : SAISIE RÈGLEMENTS ---
    with tab_reglements:
        st.subheader("Enregistrement des Flux (Entrées / Sorties)")
        if not can_write:
            st.info("🔒 Mode lecture seule.")
        elif df_comptes.empty:
            st.warning("Veuillez d'abord créer au moins un Compte/Caisse dans l'onglet précédent.")
        else:
            with st.form("form_saisie_reglement"):
                c_type, c_date = st.columns(2)
                type_flux = c_type.radio("Type d'opération", ["ENCAISSEMENT", "DECAISSEMENT"], horizontal=True)
                date_reg = c_date.date_input("Date de l'opération")

                c_part, c_cpt = st.columns(2)
                if type_flux == "ENCAISSEMENT":
                    dict_partenaires = {row["client_id"]: f"Client: {row['nom']} ({row['client_id']})" for _, row in df_clients.iterrows()} if not df_clients.empty else {}
                else:
                    dict_partenaires = {row["fournisseur_id"]: f"Fournisseur: {row['nom']} ({row['fournisseur_id']})" for _, row in df_fournisseurs.iterrows()} if not df_fournisseurs.empty else {}

                partenaire_id = c_part.selectbox("Partenaire", options=list(dict_partenaires.keys()), format_func=lambda x: dict_partenaires[x])
                dict_comptes = {row["compte_id"]: f"{row['nom_compte']} ({row['type_compte']})" for _, row in df_comptes.iterrows()}
                compte_id = c_cpt.selectbox("Compte de trésorerie impacté", options=list(dict_comptes.keys()), format_func=lambda x: dict_comptes[x])

                c_mode, c_ref, c_mont = st.columns(3)
                mode_paiement = c_mode.selectbox("Mode de paiement", liste_modes)
                reference = c_ref.text_input("Référence (N° Chèque, Tracabilité)")
                montant = c_mont.number_input("Montant total (DZD)", min_value=1.0, step=100.0)

                if st.form_submit_button("Enregistrer le flux", type="primary"):
                    if partenaire_id and compte_id:
                        reg_id = enregistrer_reglement(str(date_reg), type_flux, partenaire_id, compte_id, mode_paiement, reference, montant)
                        st.success(f"✅ Règlement {reg_id} enregistré avec succès !")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error("Veuillez sélectionner un partenaire et un compte.")

    # --- TAB 4 : LETTRAGE ---
    with tab_lettrage:
        st.subheader("Lettrage des Factures (Affectation des Règlements)")
        if not can_write:
            st.info("🔒 Mode lecture seule.")
        elif df_reg.empty:
            st.info("Aucun règlement disponible pour le lettrage.")
        else:
            df_reg["montant_total"] = pd.to_numeric(df_reg["montant_total"], errors="coerce").fillna(0)
            df_reg["montant_alloue"] = pd.to_numeric(df_reg["montant_alloue"], errors="coerce").fillna(0)
            df_reg_ouverts = df_reg[df_reg["montant_total"] > df_reg["montant_alloue"]]

            df_fac = pd.DataFrame(fetch_data("factures"))
            df_fac_ouvertes = pd.DataFrame()
            if not df_fac.empty:
                df_fac["montant_ttc"] = pd.to_numeric(df_fac["montant_ttc"], errors="coerce").fillna(0)
                df_fac["montant_paye"] = pd.to_numeric(df_fac["montant_paye"], errors="coerce").fillna(0)
                df_fac_ouvertes = df_fac[df_fac["montant_ttc"] > df_fac["montant_paye"]]

            if df_reg_ouverts.empty:
                st.success("Tous les règlements ont été entièrement alloués.")
            elif df_fac_ouvertes.empty:
                st.info("Toutes les factures sont payées.")
            else:
                with st.form("form_lettrage"):
                    c1, c2 = st.columns(2)
                    dict_regs = {r['reglement_id']: f"{r['reglement_id']} | Reste: {r['montant_total'] - r['montant_alloue']:,.2f} DZD ({r['partenaire_id']})" for _, r in df_reg_ouverts.iterrows()}
                    dict_facs = {f['facture_id']: f"{f['facture_id']} | À Payer: {f['montant_ttc'] - f['montant_paye']:,.2f} DZD ({f['client_id']})" for _, f in df_fac_ouvertes.iterrows()}

                    reg_choisi = c1.selectbox("1. Règlement en attente", options=list(dict_regs.keys()), format_func=lambda x: dict_regs[x])
                    fac_choisie = c2.selectbox("2. Facture à solder", options=list(dict_facs.keys()), format_func=lambda x: dict_facs[x])
                    montant_appliquer = st.number_input("3. Montant à imputer sur cette facture (DZD)", min_value=1.0, step=100.0)

                    if st.form_submit_button("Lier le règlement à la facture", type="primary"):
                        try:
                            enregistrer_lettrage(reg_choisi, fac_choisie, "FactureClient", montant_appliquer)
                            st.success("✅ Lettrage effectué avec succès !")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Erreur de lettrage : {e}")

    # --- TAB 5 : GRAND LIVRE COMPTABLE ---
    with tab_livre:
        st.subheader("📖 Grand Livre Comptable (`ecritures_comptables`)")
        df_ecritures = get_ecritures_comptables()

        if df_ecritures.empty:
            st.info("Aucune écriture comptable générée.")
        else:
            tot_debit = pd.to_numeric(df_ecritures.get("debit", 0), errors="coerce").fillna(0).sum()
            tot_credit = pd.to_numeric(df_ecritures.get("credit", 0), errors="coerce").fillna(0).sum()

            cd1, cd2, cd3 = st.columns(3)
            cd1.metric("Total Débit", f"{tot_debit:,.2f} DZD")
            cd2.metric("Total Crédit", f"{tot_credit:,.2f} DZD")
            cd3.metric("Balance", f"{(tot_debit - tot_credit):,.2f} DZD", delta="Équilibrée" if tot_debit == tot_credit else "Écart")

            st.dataframe(df_ecritures.sort_values(by="date_ecriture", ascending=False), use_container_width=True, hide_index=True)