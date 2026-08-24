"""
Interface utilisateur du module Dashboards.
Affiche les indicateurs de performance (KPI) de l'entreprise.
"""
import streamlit as st
import pandas as pd
import datetime
from config.roles import has_permission
from modules.dashboards.service import (
    get_kpis_direction, get_kpis_pnl, get_kpis_ventes, get_kpis_achats,
    get_kpis_stocks, get_kpis_production, get_kpis_crm,
    get_kpis_rh, get_kpis_finance
)

def show_dashboards_page():
    st.title("📊 Tableaux de bord & KPIs")

    user_role = st.session_state.get("user", {}).get("role", "")
    can_read = has_permission(user_role, "Dashboards", "lecture")

    if not can_read:
        st.error("🔒 Vous n'avez pas accès en lecture à ce module.")
        return

    # L'onglet Rentabilité a été ajouté en deuxième position
    onglets = st.tabs([
        "👑 Vue Direction", "📈 Rentabilité (P&L)", "🛒 Ventes & Facturation", "📦 Achats",
        "🏭 Stocks", "⚙️ Production", "🤝 CRM", "👥 RH", "🏦 Finance"
    ])

    # --- 1. VUE DIRECTION ---
    with onglets[0]:
        st.subheader("Santé de l'entreprise (Temps Réel)")
        kpis = get_kpis_direction()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("CA HT du mois", f"{kpis['ca_mois']:,.2f} DZD")
        col2.metric("Trésorerie Disponible", f"{kpis['tresorerie']:,.2f} DZD")
        col3.metric("Impayés (> 30 jours)", f"{kpis['impayes_30j']:,.2f} DZD", delta="À recouvrer", delta_color="inverse")
        col4.metric("Alertes Stock", str(kpis['alertes_stock']), delta="Critique" if kpis['alertes_stock'] > 0 else "Normal", delta_color="inverse")
        st.divider()

    # --- 2. RENTABILITÉ (P&L) ---
    with onglets[1]:
        st.subheader("Compte de Résultat Simplifié (P&L)")
        c_deb_pnl, c_fin_pnl = st.columns(2)
        date_deb_pnl = c_deb_pnl.date_input("Date de début", datetime.date.today().replace(day=1), key="d_pnl")
        date_fin_pnl = c_fin_pnl.date_input("Date de fin", datetime.date.today(), key="f_pnl")

        if date_deb_pnl <= date_fin_pnl:
            ts_deb_pnl, ts_fin_pnl = pd.Timestamp(date_deb_pnl), pd.Timestamp(date_fin_pnl) + pd.Timedelta(days=1, seconds=-1)
            pnl = get_kpis_pnl(ts_deb_pnl, ts_fin_pnl)

            col_pnl1, col_pnl2, col_pnl3 = st.columns(3)
            col_pnl1.metric("Chiffre d'Affaires (CA HT)", f"{pnl['ca_ht']:,.2f} DZD")
            col_pnl2.metric("Marge Brute", f"{pnl['marge_brute']:,.2f} DZD", f"{pnl['taux_marge_brute']:.1f} %")
            col_pnl3.metric("EBITDA (Résultat d'Exploitation)", f"{pnl['ebitda']:,.2f} DZD", f"{pnl['taux_ebitda']:.1f} %")

            st.divider()
            st.markdown("### Détail de la cascade des coûts")

            df_cascade = pd.DataFrame({
                "Catégorie": ["1. Revenus (CA HT)", "2. Coût des Marchandises (COGS)", "3. OPEX (Services & Loyer)", "4. OPEX (Salaires)", "5. EBITDA"],
                "Montant (DZD)": [pnl['ca_ht'], -pnl['cogs'], -pnl['opex_fournisseurs'], -pnl['opex_salaires'], pnl['ebitda']]
            })
            st.dataframe(df_cascade, use_container_width=True, hide_index=True)
            st.info("💡 Astuce : Pour que vos frais généraux (électricité, loyer) apparaissent ici, créez vos fournisseurs dans le module Administration avec une catégorie contenant le mot 'OPEX', puis enregistrez leurs paiements dans la Trésorerie.")

    # --- 3. VENTES & FACTURATION ---
    with onglets[2]:
        st.subheader("Analyse des Ventes & Recouvrement")
        c_deb, c_fin = st.columns(2)
        date_deb = c_deb.date_input("Date de début", datetime.date.today().replace(day=1), key="d_v")
        date_fin = c_fin.date_input("Date de fin", datetime.date.today(), key="f_v")

        if date_deb <= date_fin:
            ts_deb, ts_fin = pd.Timestamp(date_deb), pd.Timestamp(date_fin) + pd.Timedelta(days=1, seconds=-1)
            kpis_v = get_kpis_ventes(ts_deb, ts_fin)

            cv1, cv2, cv3, cv4 = st.columns(4)
            cv1.metric("CA Période (HT)", f"{kpis_v['ca_ht']:,.2f} DZD")
            cv2.metric("CA Période (TTC)", f"{kpis_v['ca_ttc']:,.2f} DZD")
            cv3.metric("Panier Moyen (TTC)", f"{kpis_v['panier_moyen']:,.2f} DZD")
            cv4.metric("Taux d'Avoirs", f"{kpis_v['taux_avoirs']:.1f} %", delta="Retours/Annulations", delta_color="inverse")
            st.divider()

            col_g1, col_g2 = st.columns(2)
            with col_g1:
                st.markdown("**Balance Âgée (Créances)**")
                df_balance = pd.DataFrame(list(kpis_v["balance_agee"].items()), columns=["Tranche", "Montant (DZD)"])
                st.bar_chart(df_balance.set_index("Tranche"))
            with col_g2:
                st.markdown("**Top Clients**")
                if not kpis_v["top_clients"].empty:
                    st.dataframe(kpis_v["top_clients"], use_container_width=True, hide_index=True)

    # --- 4. ACHATS ---
    with onglets[3]:
        st.subheader("Analyse des Achats & Fournisseurs")
        c_deb_a, c_fin_a = st.columns(2)
        date_deb_a = c_deb_a.date_input("Date de début", datetime.date.today().replace(day=1), key="d_a")
        date_fin_a = c_fin_a.date_input("Date de fin", datetime.date.today(), key="f_a")

        if date_deb_a <= date_fin_a:
            ts_deb_a, ts_fin_a = pd.Timestamp(date_deb_a), pd.Timestamp(date_fin_a) + pd.Timedelta(days=1, seconds=-1)
            kpis_a = get_kpis_achats(ts_deb_a, ts_fin_a)

            ca1, ca2 = st.columns(2)
            ca1.metric("Montant Total Achats", f"{kpis_a['montant_total']:,.2f} DZD")
            ca2.metric("Commandes en retard", str(kpis_a['commandes_retard']), delta="À relancer" if kpis_a['commandes_retard'] > 0 else "OK", delta_color="inverse")
            st.divider()

            col_ga1, col_ga2 = st.columns(2)
            with col_ga1:
                st.markdown("**Concentration Fournisseurs**")
                df_rep = kpis_a["repartition_fournisseurs"]
                if not df_rep.empty:
                    st.bar_chart(df_rep.set_index("fournisseur_id")[df_rep.columns[1]])
            with col_ga2:
                st.markdown("**Évolution des Prix d'Achat**")
                df_evo = kpis_a["evolution_prix"]
                if not df_evo.empty:
                    mp_choisie = st.selectbox("Sélectionnez une Matière", options=df_evo["mp_id"].unique().tolist())
                    st.line_chart(df_evo[df_evo["mp_id"] == mp_choisie].sort_values(by="date_obj").set_index("date_obj")["prix_unitaire"])

    # --- 5. STOCKS ---
    with onglets[4]:
        st.subheader("Analyse Financière des Stocks")
        jours = st.slider("Fenêtre d'alerte péremption (Jours)", 7, 120, 30, 7)
        kpis_s = get_kpis_stocks(jours_alerte_peremption=jours)

        cs1, cs2, cs3 = st.columns(3)
        cs1.metric("Valeur Totale Immobilisée", f"{kpis_s['valeur_totale']:,.2f} DZD")
        cs2.metric("Mat. Premières (Sous seuil)", str(kpis_s['sous_seuil']), delta="Rupture imminente" if kpis_s['sous_seuil']>0 else "OK", delta_color="inverse")
        cs3.metric(f"Lots expirant d'ici {jours}j", str(len(kpis_s['lots_expirants'])), delta="Urgent" if len(kpis_s['lots_expirants'])>0 else "OK", delta_color="inverse")
        st.divider()

        c_st1, c_st2 = st.columns(2)
        with c_st1:
            st.markdown("**Répartition de la Valeur**")
            st.bar_chart(pd.DataFrame([{"Catégorie": "MP", "Valeur": kpis_s['valeur_mp']}, {"Catégorie": "PF", "Valeur": kpis_s['valeur_pf']}]).set_index("Catégorie"))
        with c_st2:
            st.markdown("**Détail des lots à risque**")
            st.dataframe(kpis_s["lots_expirants"], use_container_width=True, hide_index=True) if not kpis_s["lots_expirants"].empty else st.success("Aucun risque.")

    # --- 6. PRODUCTION ---
    with onglets[5]:
        st.subheader("Performance de Production")
        c_deb_p, c_fin_p = st.columns(2)
        date_deb_p = c_deb_p.date_input("Date de début", datetime.date.today().replace(day=1), key="d_p")
        date_fin_p = c_fin_p.date_input("Date de fin", datetime.date.today(), key="f_p")

        if date_deb_p <= date_fin_p:
            ts_deb_p, ts_fin_p = pd.Timestamp(date_deb_p), pd.Timestamp(date_fin_p) + pd.Timedelta(days=1, seconds=-1)
            kpis_p = get_kpis_production(ts_deb_p, ts_fin_p)

            cp1, cp2 = st.columns(2)
            cp1.metric("Ordres de Fabrication (OF)", str(kpis_p['total_ofs']))
            cp2.metric("Taux de Rejet (CQ)", f"{kpis_p['taux_rejet']:.1f} %", delta="Non-conformité" if kpis_p['taux_rejet']>5 else "Normal", delta_color="inverse")
            st.divider()

            st.markdown("**Répartition des OF par Statut**")
            if not kpis_p["repartition_statut"].empty:
                st.bar_chart(kpis_p["repartition_statut"].set_index("Statut"))

    # --- 7. CRM ---
    with onglets[6]:
        st.subheader("Performance Commerciale & Pipeline")
        c_deb_c, c_fin_c = st.columns(2)
        date_deb_c = c_deb_c.date_input("Date de début", datetime.date.today().replace(day=1), key="d_c")
        date_fin_c = c_fin_c.date_input("Date de fin", datetime.date.today(), key="f_c")

        if date_deb_c <= date_fin_c:
            ts_deb_c, ts_fin_c = pd.Timestamp(date_deb_c), pd.Timestamp(date_fin_c) + pd.Timedelta(days=1, seconds=-1)
            kpis_c = get_kpis_crm(ts_deb_c, ts_fin_c)

            cc1, cc2 = st.columns(2)
            cc1.metric("Pipeline Pondéré (En cours)", f"{kpis_c['pipeline_pondere']:,.2f} DZD", help="Valeur estimée * Probabilité des opportunités non clôturées.")
            cc2.metric("Taux de Conversion (Période)", f"{kpis_c['taux_conversion']:.1f} %", help="Opportunités gagnées / Opportunités clôturées")
            st.divider()

            st.markdown("**Top Commerciaux (CA Généré)**")
            if not kpis_c["performance_commerciaux"].empty:
                st.bar_chart(kpis_c["performance_commerciaux"].set_index("Commercial"))
            else:
                st.info("Aucune opportunité gagnée sur cette période.")

    # --- 8. RH ---
    with onglets[7]:
        st.subheader("Ressources Humaines")
        kpis_r = get_kpis_rh(pd.Timestamp("2000-01-01"), pd.Timestamp("2100-01-01"))

        cr1, cr2 = st.columns(2)
        cr1.metric("Effectif Actif", str(kpis_r["effectif_actif"]))
        cr2.metric("Congés en attente de validation", str(kpis_r["conges_attente"]), delta="À traiter" if kpis_r["conges_attente"]>0 else "OK", delta_color="inverse")
        st.divider()

        st.markdown("**Répartition par Service**")
        if not kpis_r["repartition_service"].empty:
            st.bar_chart(kpis_r["repartition_service"].set_index("Service"))
        else:
            st.info("Aucune donnée d'employés.")

    # --- 9. FINANCE ---
    with onglets[8]:
        st.subheader("Flux de Trésorerie & Rapprochement")
        c_deb_f, c_fin_f = st.columns(2)
        date_deb_f = c_deb_f.date_input("Date de début", datetime.date.today().replace(day=1), key="d_f")
        date_fin_f = c_fin_f.date_input("Date de fin", datetime.date.today(), key="f_f")

        if date_deb_f <= date_fin_f:
            ts_deb_f, ts_fin_f = pd.Timestamp(date_deb_f), pd.Timestamp(date_fin_f) + pd.Timedelta(days=1, seconds=-1)
            kpis_f = get_kpis_finance(ts_deb_f, ts_fin_f)

            cf1, cf2, cf3 = st.columns(3)
            cf1.metric("Flux Entrants", f"{kpis_f['flux_entrants']:,.2f} DZD")
            cf2.metric("Flux Sortants", f"{kpis_f['flux_sortants']:,.2f} DZD", delta_color="inverse")
            cf3.metric("Taux de Lettrage", f"{kpis_f['taux_lettrage']:.1f} %", help="% des encaissements rattachés à des factures.")
            st.divider()

            st.markdown("**Répartition de la Trésorerie par Compte (Solde Initial)**")
            if not kpis_f["repartition_comptes"].empty:
                df_pie = kpis_f["repartition_comptes"].set_index("nom_compte")["solde"]
                st.bar_chart(df_pie)
            else:
                st.info("Aucun compte financier configuré.")