"""
Interface utilisateur du module Dashboards.
Affiche les indicateurs de performance (KPI) de l'entreprise.
"""
import streamlit as st
from modules.help.contextual import show_context_help, topic_help, field_help
import pandas as pd
import datetime
from config.roles import has_permission
from core.strict_reads import read_section
from modules.dashboards.service import (
    get_kpis_direction, get_kpis_pnl, get_kpis_ventes, get_kpis_achats,
    get_kpis_stocks, get_kpis_production, get_kpis_crm,
    get_kpis_rh, get_kpis_finance
)

def _current_month_end(today: datetime.date) -> datetime.date:
    """P&L mensuel : la période par défaut couvre toujours un mois entier.

    Les nets de paie enregistrés sont mensuels et non proratisables.
    """
    next_month = (today.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
    return next_month - datetime.timedelta(days=1)


def _mark_dashboards_activity() -> None:
    """Signale une selection sans renouveler directement la session."""
    st.session_state["_erp_dashboards_interacted"] = True


def show_dashboards_page():
    from modules.dashboards.service import dashboard_read_scope
    with dashboard_read_scope():
        return _show_dashboards_page_impl()


def _show_dashboards_page_impl():
    st.title("📊 Tableaux de bord & KPIs")
    st.caption("Version Dashboards : SOF-ERP-20261101-READ-01 / SOF-ERP-20261102-KPI-05")

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
    with onglets[0], read_section("Direction"):
        st.subheader("Santé de l'entreprise (Temps Réel)", help=topic_help("dashboard.direction"))
        show_context_help(st, "dashboard.direction")
        st.caption("Facturation brute : factures clients validées, hors avoirs, brouillons et annulations.")
        st.caption("Trésorerie : Banque/Caisse, soldes initiaux + règlements validés jusqu’à aujourd’hui ; hors autres écritures et rapprochement bancaire.")
        kpis = get_kpis_direction()

        # Allouer plus de largeur aux montants de trésorerie et aux impayés.
        col1, col2, col3, col4 = st.columns([1.05, 1.50, 1.25, 0.60])
        col1.metric("Facturation brute HT du mois", f"{kpis['ca_mois']:,.2f} DZD")
        col2.metric("Trésorerie indicative", f"{kpis['tresorerie']:,.2f} DZD")
        col3.metric("Impayés (> 30 jours)", f"{kpis['impayes_30j']:,.2f} DZD", delta="À recouvrer", delta_color="inverse")
        col4.metric("Alertes Stock", str(kpis['alertes_stock']), delta="Critique" if kpis['alertes_stock'] > 0 else "Normal", delta_color="inverse")
        if kpis.get("seuils_stock_absents", 0):
            st.warning(f"{kpis['seuils_stock_absents']} matière(s) en stock sans seuil minimum configuré : ces références ne peuvent pas être évaluées pour les alertes.")
        st.divider()

    # --- 2. RENTABILITÉ (P&L) ---
    with onglets[1], read_section("Rentabilité"):
        st.subheader("Estimation de gestion (P&L)", help=topic_help("dashboard.pnl"))
        show_context_help(st, "dashboard.pnl")
        st.caption("Facturation brute validée hors avoirs et coûts produits actuels, non historiques. OPEX = décaissements validés classés OPEX. Paie = nets enregistrés des mois sélectionnés, tous statuts de paiement, sans cotisations employeur ni preuve de validation. Choisir des mois complets si des fiches existent ; aucun prorata journalier. Ce solde mélange facturation et décaissements : il ne constitue pas un résultat comptable.")
        c_deb_pnl, c_fin_pnl = st.columns(2)
        date_deb_pnl = c_deb_pnl.date_input("Date de début", datetime.date.today().replace(day=1), key="d_pnl", on_change=_mark_dashboards_activity)
        date_fin_pnl = c_fin_pnl.date_input("Date de fin", _current_month_end(datetime.date.today()), key="f_pnl", on_change=_mark_dashboards_activity)

        if date_deb_pnl <= date_fin_pnl:
            ts_deb_pnl, ts_fin_pnl = pd.Timestamp(date_deb_pnl), pd.Timestamp(date_fin_pnl) + pd.Timedelta(days=1, seconds=-1)
            pnl = get_kpis_pnl(ts_deb_pnl, ts_fin_pnl)

            col_pnl1, col_pnl2, col_pnl3 = st.columns(3)
            col_pnl1.metric("Facturation brute HT", f"{pnl['ca_ht']:,.2f} DZD")
            col_pnl2.metric("Marge Brute", f"{pnl['marge_brute']:,.2f} DZD", f"{pnl['taux_marge_brute']:.1f} %")
            col_pnl3.metric("Solde de gestion estimatif", f"{pnl['ebitda']:,.2f} DZD", f"{pnl['taux_ebitda']:.1f} %")

            st.divider()
            st.markdown("### Détail de la cascade des coûts")

            df_cascade = pd.DataFrame({
                "Catégorie": ["1. Facturation brute HT", "2. Coût des Marchandises (COGS)", "3. Décaissements fournisseurs OPEX", "4. Nets mensuels enregistrés", "5. Solde estimatif"],
                "Montant (DZD)": [pnl['ca_ht'], -pnl['cogs'], -pnl['opex_fournisseurs'], -pnl['opex_salaires'], pnl['ebitda']]
            })
            st.dataframe(df_cascade, use_container_width=True, hide_index=True)
            st.info("💡 Astuce : Pour que vos frais généraux (électricité, loyer) apparaissent ici, créez vos fournisseurs dans le module Administration avec une catégorie contenant le mot 'OPEX', puis enregistrez leurs paiements dans la Trésorerie.")

    # --- 3. VENTES & FACTURATION ---
    with onglets[2], read_section("Ventes"):
        st.subheader("Analyse des Ventes & Recouvrement", help=topic_help("dashboard.ventes"))
        show_context_help(st, "dashboard.ventes")
        st.caption("Factures validées uniquement. Facturation brute hors avoirs ; ratio des avoirs validés suivi séparément. Créances globales, indépendantes de la période sélectionnée.")
        c_deb, c_fin = st.columns(2)
        date_deb = c_deb.date_input("Date de début", datetime.date.today().replace(day=1), key="d_v", on_change=_mark_dashboards_activity)
        date_fin = c_fin.date_input("Date de fin", datetime.date.today(), key="f_v", on_change=_mark_dashboards_activity)

        if date_deb <= date_fin:
            ts_deb, ts_fin = pd.Timestamp(date_deb), pd.Timestamp(date_fin) + pd.Timedelta(days=1, seconds=-1)
            kpis_v = get_kpis_ventes(ts_deb, ts_fin)

            cv1, cv2, cv3, cv4 = st.columns(4)
            cv1.metric("Facturation brute HT", f"{kpis_v['ca_ht']:,.2f} DZD")
            cv2.metric("Facturation brute TTC", f"{kpis_v['ca_ttc']:,.2f} DZD")
            cv3.metric("Panier Moyen (TTC)", f"{kpis_v['panier_moyen']:,.2f} DZD")
            cv4.metric("Taux d'Avoirs", f"{kpis_v['taux_avoirs']:.1f} %", delta="Retours/Annulations", delta_color="inverse")
            st.divider()

            col_g1, col_g2 = st.columns(2)
            with col_g1:
                st.markdown("**Balance Âgée (Créances)**")
                df_balance = pd.DataFrame(list(kpis_v["balance_agee"].items()), columns=["Tranche", "Montant (DZD)"])
                st.bar_chart(df_balance.set_index("Tranche"), horizontal=True)
            with col_g2:
                st.markdown("**Top Clients**")
                if not kpis_v["top_clients"].empty:
                    st.dataframe(kpis_v["top_clients"], use_container_width=True, hide_index=True)

    # --- 4. ACHATS ---
    with onglets[3], read_section("Achats"):
        st.subheader("Analyse des Achats & Fournisseurs", help=topic_help("dashboard.achats"))
        show_context_help(st, "dashboard.achats")
        st.caption("Retards globaux, indépendants de la période : commandes en attente ou partiellement réceptionnées, échéance antérieure à aujourd’hui.")
        c_deb_a, c_fin_a = st.columns(2)
        date_deb_a = c_deb_a.date_input("Date de début", datetime.date.today().replace(day=1), key="d_a", on_change=_mark_dashboards_activity)
        date_fin_a = c_fin_a.date_input("Date de fin", datetime.date.today(), key="f_a", on_change=_mark_dashboards_activity)

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
                    st.bar_chart(df_rep.set_index("fournisseur_id")[df_rep.columns[1]], horizontal=True)
            with col_ga2:
                st.markdown("**Évolution des Prix d'Achat**")
                df_evo = kpis_a["evolution_prix"]
                if not df_evo.empty:
                    mp_choisie = st.selectbox("Sélectionnez une Matière", options=df_evo["mp_id"].unique().tolist(), on_change=_mark_dashboards_activity)
                    st.line_chart(df_evo[df_evo["mp_id"] == mp_choisie].sort_values(by="date_obj").set_index("date_obj")["prix_unitaire"])

    # --- 5. STOCKS ---
    with onglets[4], read_section("Stocks"):
        st.subheader("Analyse Financière des Stocks", help=topic_help("dashboard.stocks"))
        show_context_help(st, "dashboard.stocks")
        jours = st.slider("Fenêtre d'alerte péremption (Jours)", 7, 120, 30, 7, on_change=_mark_dashboards_activity)
        kpis_s = get_kpis_stocks(jours_alerte_peremption=jours)

        if kpis_s.get("lots_sans_date", 0):
            st.warning(f"{kpis_s['lots_sans_date']} lot(s) avec stock sans date de péremption : risque non évalué.")
        if kpis_s.get("seuils_stock_absents", 0):
            st.warning(f"{kpis_s['seuils_stock_absents']} matière(s) en stock sans seuil minimum : alerte de rupture non évaluable pour ces références.")
        cs1, cs2, cs3 = st.columns(3)
        cs1.metric("Valeur Totale Immobilisée", f"{kpis_s['valeur_totale']:,.2f} DZD")
        cs2.metric("Mat. Premières (Sous seuil)", str(kpis_s['sous_seuil']), delta="Rupture imminente" if kpis_s['sous_seuil']>0 else "OK", delta_color="inverse")
        cs3.metric(f"Lots périmés ou échéance ≤ {jours}j", str(len(kpis_s['lots_expirants'])), delta="Urgent" if len(kpis_s['lots_expirants'])>0 else "OK", delta_color="inverse")
        st.divider()

        c_st1, c_st2 = st.columns(2)
        with c_st1:
            st.markdown("**Répartition de la Valeur**")
            st.bar_chart(pd.DataFrame([{"Catégorie": "MP", "Valeur": kpis_s['valeur_mp']}, {"Catégorie": "PF", "Valeur": kpis_s['valeur_pf']}]).set_index("Catégorie"))
        with c_st2:
            st.markdown("**Détail des lots à risque**")
            st.dataframe(kpis_s["lots_expirants"], use_container_width=True, hide_index=True) if not kpis_s["lots_expirants"].empty else st.info("Aucun lot daté dans la fenêtre d’alerte.")

    # --- 6. PRODUCTION ---
    with onglets[5], read_section("Production"):
        st.subheader("Performance de Production", help=topic_help("dashboard.production"))
        show_context_help(st, "dashboard.production")
        c_deb_p, c_fin_p = st.columns(2)
        date_deb_p = c_deb_p.date_input("Date de début", datetime.date.today().replace(day=1), key="d_p", on_change=_mark_dashboards_activity)
        date_fin_p = c_fin_p.date_input("Date de fin", datetime.date.today(), key="f_p", on_change=_mark_dashboards_activity)

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
    with onglets[6], read_section("CRM"):
        st.subheader("Performance Commerciale & Pipeline", help=topic_help("dashboard.crm"))
        show_context_help(st, "dashboard.crm")
        st.caption("Pipeline ouvert global. Conversion et valeurs gagnées : opportunités créées dans la période, selon leur statut actuel ; ce ne sont pas des ventes facturées ni des clôtures datées.")
        c_deb_c, c_fin_c = st.columns(2)
        date_deb_c = c_deb_c.date_input("Date de début", datetime.date.today().replace(day=1), key="d_c", on_change=_mark_dashboards_activity)
        date_fin_c = c_fin_c.date_input("Date de fin", datetime.date.today(), key="f_c", on_change=_mark_dashboards_activity)

        if date_deb_c <= date_fin_c:
            ts_deb_c, ts_fin_c = pd.Timestamp(date_deb_c), pd.Timestamp(date_fin_c) + pd.Timedelta(days=1, seconds=-1)
            kpis_c = get_kpis_crm(ts_deb_c, ts_fin_c)

            cc1, cc2 = st.columns(2)
            cc1.metric("Pipeline Pondéré (En cours)", f"{kpis_c['pipeline_pondere']:,.2f} DZD", help="Valeur estimée * Probabilité des opportunités non clôturées.")
            cc2.metric("Taux de Conversion (Période)", f"{kpis_c['taux_conversion']:.1f} %", help="Gagnées / (gagnées + perdues), parmi les opportunités créées dans la période.")
            st.divider()

            st.markdown("**Valeur estimée des opportunités gagnées par commercial**")
            if not kpis_c["performance_commerciaux"].empty:
                st.bar_chart(kpis_c["performance_commerciaux"].set_index("Commercial"))
            else:
                st.info("Aucune opportunité actuellement gagnée parmi celles créées dans la période.")

    # --- 8. RH ---
    with onglets[7], read_section("RH"):
        st.subheader("Ressources Humaines", help=topic_help("dashboard.rh"))
        show_context_help(st, "dashboard.rh")
        st.caption("Effectif actuel : employés marqués actif = OUI. Services non renseignés affichés séparément.")
        kpis_r = get_kpis_rh(pd.Timestamp("2000-01-01"), pd.Timestamp("2100-01-01"))

        cr1, cr2 = st.columns(2)
        cr1.metric("Effectif Actif", str(kpis_r["effectif_actif"]))
        cr2.metric("Congés en attente de validation", str(kpis_r["conges_attente"]), delta="À traiter" if kpis_r["conges_attente"]>0 else "OK", delta_color="inverse")
        st.divider()

        st.markdown("**Répartition par Service**")
        if not kpis_r["repartition_service"].empty:
            st.bar_chart(kpis_r["repartition_service"].set_index("Service"), horizontal=True)
        else:
            st.info("Aucune donnée d'employés.")

    # --- 9. FINANCE ---
    with onglets[8], read_section("Finance"):
        st.subheader("Flux de Trésorerie & Rapprochement", help=topic_help("dashboard.finance"))
        show_context_help(st, "dashboard.finance")
        c_deb_f, c_fin_f = st.columns(2)
        date_deb_f = c_deb_f.date_input("Date de début", datetime.date.today().replace(day=1), key="d_f", on_change=_mark_dashboards_activity)
        date_fin_f = c_fin_f.date_input("Date de fin", datetime.date.today(), key="f_f", on_change=_mark_dashboards_activity)

        if date_deb_f <= date_fin_f:
            ts_deb_f, ts_fin_f = pd.Timestamp(date_deb_f), pd.Timestamp(date_fin_f) + pd.Timedelta(days=1, seconds=-1)
            kpis_f = get_kpis_finance(ts_deb_f, ts_fin_f)

            cf1, cf2, cf3 = st.columns(3)
            cf1.metric("Flux Entrants", f"{kpis_f['flux_entrants']:,.2f} DZD")
            cf2.metric("Flux Sortants", f"{kpis_f['flux_sortants']:,.2f} DZD", delta_color="inverse")
            cf3.metric("Taux de Lettrage", f"{kpis_f['taux_lettrage']:.1f} %", help="% des encaissements rattachés à des factures.")
            st.divider()

            st.markdown("**Soldes indicatifs Banque/Caisse à ce jour**")
            st.caption("Soldes initiaux + règlements VALIDE jusqu’à aujourd’hui, indépendants du filtre des flux. Comptes tiers exclus ; hors autres écritures et rapprochement bancaire. Les soldes initiaux ne sont pas datés dans le référentiel.")
            if not kpis_f["repartition_comptes"].empty:
                df_pie = kpis_f["repartition_comptes"].assign(compte=lambda df: df["compte_id"].astype(str) + " — " + df["nom_compte"].astype(str)).set_index("compte")["solde"]
                st.bar_chart(df_pie, horizontal=True)
            else:
                st.info("Aucun compte financier configuré.")