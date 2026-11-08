"""
Interface utilisateur du module Dashboards.
Affiche les indicateurs de performance (KPI) de l'entreprise.
"""
import streamlit as st
from modules.help.contextual import show_context_help, topic_help, field_help
import pandas as pd
import datetime
import plotly.graph_objects as go
from config.roles import has_permission
from core.strict_reads import DataReadError, read_section
from core.query_diagnostics import query_metrics_snapshot
from modules.dashboards.demo import SCENARIO_VERSION, build_demo_dataset
from core.utils import get_local_now
from modules.dashboards.service import (
    get_kpis_direction, get_kpis_pnl, get_kpis_ventes, get_kpis_achats,
    get_kpis_stocks, get_kpis_production, get_kpis_crm,
    get_kpis_rh, get_kpis_finance, get_dashboard_data_provenance
)

_DASHBOARD_PANELS = (
    "👑 Vue Direction", "📈 Rentabilité (P&L)", "🛒 Ventes & Facturation",
    "📦 Achats", "🏭 Stocks", "⚙️ Production", "🤝 CRM", "👥 RH",
    "🏦 Finance",
)


def _dashboard_today() -> datetime.date:
    """Référence calendrier ERP, identique aux dates des calculs métier."""
    return get_local_now().date()


def _current_month_end(today: datetime.date) -> datetime.date:
    """P&L mensuel : la période par défaut couvre toujours un mois entier.

    Les nets de paie enregistrés sont mensuels et non proratisables.
    """
    next_month = (today.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
    return next_month - datetime.timedelta(days=1)


def _rate_or_na(rate: float, denominator: int | float) -> str:
    """Zéro avec dénominateur absent n'est pas un KPI à 0 %."""
    return f"{rate:.1f} %" if denominator > 0 else "N/D"


def _show_management_waterfall(st, pnl: dict) -> None:
    """Cascade de gestion indicatrice : jamais un EBITDA comptable."""
    labels = ["Facturation HT", "COGS au coût actuel", "OPEX payées",
              "Nets de paie enregistrés", "Solde estimatif"]
    fig = go.Figure(go.Waterfall(
        x=labels,
        y=[pnl["ca_ht"], -pnl["cogs"], -pnl["opex_fournisseurs"],
           -pnl["opex_salaires"], 0],
        # La dernière barre est calculée par Plotly avec y=0. Le tooltip
        # doit afficher le vrai solde, pas cette valeur technique.
        customdata=[pnl["ca_ht"], -pnl["cogs"], -pnl["opex_fournisseurs"],
                    -pnl["opex_salaires"], pnl["ebitda"]],
        measure=["absolute", "relative", "relative", "relative", "total"],
        connector={"line": {"width": 1}},
        hovertemplate="%{x} : %{customdata:,.2f} DZD<extra></extra>",
    ))
    fig.update_layout(
        title="Reconstitution du solde de gestion (DZD)",
        yaxis_title="DZD", margin=dict(t=54, l=18, r=18, b=18),
        showlegend=False, height=370,
    )
    st.plotly_chart(fig, use_container_width=True,
                    config={"displayModeBar": False})


def _mark_dashboards_activity() -> None:
    """Signale une selection sans renouveler directement la session."""
    st.session_state["_erp_dashboards_interacted"] = True


def show_dashboards_page():
    from modules.dashboards.service import dashboard_read_scope
    # Sélection de source uniquement pour les neuf lectures Dashboard.
    # Aucune donnée simulée n'est enregistrée ou mêlée à Supabase.
    demo_rows = (build_demo_dataset(get_local_now())
                 if st.session_state.get("_erp_dashboard_demo_mode", False)
                 else None)
    with dashboard_read_scope(demo_rows=demo_rows):
        return _show_dashboards_page_impl()


def _show_dashboards_page_impl():
    st.title("📊 Tableaux de bord & KPIs")
    st.caption("Version Dashboards : SOF-ERP-20261107-DEMO-01 / SOF-ERP-20261102-KPI-05")

    user_role = st.session_state.get("user", {}).get("role", "")
    can_read = has_permission(user_role, "Dashboards", "lecture")

    if not can_read:
        st.error("🔒 Vous n'avez pas accès en lecture à ce module.")
        return

    # Le sélecteur doit apparaître AVANT les onglets : Streamlit place
    # les blocs dans l'ordre de création, pas dans l'ordre des "with".
    st.toggle(
        "Mode démonstration — scénarios fictifs des 9 tableaux de bord",
        key="_erp_dashboard_demo_mode",
        on_change=_mark_dashboards_activity,
        help="Activer pour remplacer toutes les lectures Dashboard par un jeu "
             "local DEMO/SIM ; aucune requête de données ni écriture Supabase. "
             "Désactiver pour retrouver la consultation normale.")
    if st.session_state.get("_erp_dashboard_demo_mode", False):
        st.warning(
            f"**MODE DÉMONSTRATION — {SCENARIO_VERSION}** : tous les chiffres "
            "et graphiques ci-dessous sont fictifs, générés uniquement en mémoire. "
            "Ils ne reflètent ni les comptes, ni le stock, ni la production réelle. "
            "Aucune écriture ou synchronisation en base.")
    else:
        # Préfixes DEMO/SIM présents dans la base réelle conservés pour le
        # développement : leur nature doit être validée avant homologation.
        try:
            provenance = get_dashboard_data_provenance()
        except (PermissionError, DataReadError):
            st.info("Provenance des données non vérifiable pour ce profil : "
                    "les KPI ne sont pas certifiés comme données réelles.")
        else:
            if provenance["marked"]:
                st.warning(
                    f"Provenance à qualifier : {provenance['marked']} référence(s) "
                    "avec préfixe DEMO/SIM détectée(s) parmi les sources métier. "
                    "Ces lignes restent incluses dans les KPI ; ne pas prendre "
                    "ces indicateurs pour des résultats d'exploitation homologués.")
                with st.expander("Voir le nombre de références DEMO/SIM par source"):
                    st.dataframe(pd.DataFrame(provenance["sources"]),
                                 use_container_width=True, hide_index=True)
                    st.caption("Ces préfixes sont des indices ; les données de "
                               "développement actuelles restent conservées "
                               "jusqu'à la finalisation de l'ERP.")

    # Streamlit calcule le contenu des neuf st.tabs même si un seul onglet
    # est actif. Ne rendre qu'une vue : aucune lecture Supabase des 8 autres.
    # Le sélecteur garde sa valeur lors du changement de source DEMO/RÉEL.
    active_panel = st.selectbox(
        "Vue du tableau de bord",
        _DASHBOARD_PANELS,
        key="_erp_dashboard_active_panel",
        on_change=_mark_dashboards_activity,
        help="Un seul tableau de bord est calculé et chargé à la fois.",
    )

    # --- 1. VUE DIRECTION ---
    if active_panel == _DASHBOARD_PANELS[0]:
        with read_section("Direction"):
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
    if active_panel == _DASHBOARD_PANELS[1]:
        with read_section("Rentabilité"):
            st.subheader("Estimation de gestion (P&L)", help=topic_help("dashboard.pnl"))
            show_context_help(st, "dashboard.pnl")
            st.caption("Facturation brute validée hors avoirs et coûts produits actuels, non historiques. OPEX = décaissements validés classés OPEX. Paie = nets enregistrés des mois sélectionnés, tous statuts de paiement, sans cotisations employeur ni preuve de validation. Choisir des mois complets si des fiches existent ; aucun prorata journalier. Ce solde mélange facturation et décaissements : il ne constitue pas un résultat comptable.")
            c_deb_pnl, c_fin_pnl = st.columns(2)
            date_deb_pnl = c_deb_pnl.date_input("Date de début", _dashboard_today().replace(day=1), key="d_pnl", on_change=_mark_dashboards_activity, help=field_help("Date de début", module="dashboards"))
            date_fin_pnl = c_fin_pnl.date_input("Date de fin", _current_month_end(_dashboard_today()), key="f_pnl", on_change=_mark_dashboards_activity, help=field_help("Date de fin", module="dashboards"))

            if date_deb_pnl <= date_fin_pnl:
                ts_deb_pnl, ts_fin_pnl = pd.Timestamp(date_deb_pnl), pd.Timestamp(date_fin_pnl) + pd.Timedelta(days=1, seconds=-1)
                pnl = get_kpis_pnl(ts_deb_pnl, ts_fin_pnl)

                col_pnl1, col_pnl2, col_pnl3 = st.columns(3)
                col_pnl1.metric("Facturation brute HT", f"{pnl['ca_ht']:,.2f} DZD")
                col_pnl2.metric(
                    "Marge brute indicative", f"{pnl['marge_brute']:,.2f} DZD",
                    _rate_or_na(pnl["taux_marge_brute"], pnl["ca_ht"]))
                col_pnl3.metric(
                    "Solde de gestion estimatif", f"{pnl['ebitda']:,.2f} DZD",
                    _rate_or_na(pnl["taux_ebitda"], pnl["ca_ht"]))

                st.divider()
                st.markdown("### Détail de la cascade des coûts")

                df_cascade = pd.DataFrame({
                    "Catégorie": ["1. Facturation brute HT", "2. Coût des Marchandises (COGS)", "3. Décaissements fournisseurs OPEX", "4. Nets mensuels enregistrés", "5. Solde estimatif"],
                    "Montant (DZD)": [pnl['ca_ht'], -pnl['cogs'], -pnl['opex_fournisseurs'], -pnl['opex_salaires'], pnl['ebitda']]
                })
                st.dataframe(df_cascade, use_container_width=True, hide_index=True)
                _show_management_waterfall(st, pnl)
                st.caption("Cascade indicative : coût PF actuel (pas un coût historique), "
                           "décaissements OPEX et nets de paie enregistrés. "
                           "Ce solde n'est ni un EBITDA comptable ni un résultat SCF.")
                st.info("💡 Astuce : Pour que vos frais généraux (électricité, loyer) apparaissent ici, créez vos fournisseurs dans le module Administration avec une catégorie contenant le mot 'OPEX', puis enregistrez leurs paiements dans la Trésorerie.")

        # --- 3. VENTES & FACTURATION ---
    if active_panel == _DASHBOARD_PANELS[2]:
        with read_section("Ventes"):
            st.subheader("Analyse des Ventes & Recouvrement", help=topic_help("dashboard.ventes"))
            show_context_help(st, "dashboard.ventes")
            st.caption("Factures validées uniquement. Facturation brute hors avoirs ; ratio des avoirs validés suivi séparément. Créances globales, indépendantes de la période sélectionnée.")
            c_deb, c_fin = st.columns(2)
            date_deb = c_deb.date_input("Date de début", _dashboard_today().replace(day=1), key="d_v", on_change=_mark_dashboards_activity, help=field_help("Date de début", module="dashboards"))
            date_fin = c_fin.date_input("Date de fin", _dashboard_today(), key="f_v", on_change=_mark_dashboards_activity, help=field_help("Date de fin", module="dashboards"))

            if date_deb <= date_fin:
                ts_deb, ts_fin = pd.Timestamp(date_deb), pd.Timestamp(date_fin) + pd.Timedelta(days=1, seconds=-1)
                kpis_v = get_kpis_ventes(ts_deb, ts_fin)

                cv1, cv2, cv3, cv4 = st.columns(4)
                cv1.metric("Facturation brute HT", f"{kpis_v['ca_ht']:,.2f} DZD")
                cv2.metric("Facturation brute TTC", f"{kpis_v['ca_ttc']:,.2f} DZD")
                cv3.metric("Panier Moyen (TTC)", f"{kpis_v['panier_moyen']:,.2f} DZD")
                cv4.metric("Avoirs / facturation brute TTC",
                           _rate_or_na(kpis_v["taux_avoirs"], kpis_v["ca_ttc"]))
                st.caption("Ce ratio suit les montants des avoirs validés, sans les "
                           "confondre avec les retours physiques. Les créances sont "
                           "globales et ne suivent pas le filtre de dates.")
                st.divider()
                st.markdown("**Évolution journalière de la facturation brute HT validée**")
                if not kpis_v["evolution_facturation"].empty:
                    st.line_chart(
                        kpis_v["evolution_facturation"].set_index("Date"),
                        use_container_width=True)
                else:
                    st.info("Aucune facture client validée sur cette période : "
                            "aucune courbe n'est construite.")
                col_g1, col_g2 = st.columns(2)
                with col_g1:
                    st.markdown("**Balance Âgée (Créances)**")
                    df_balance = pd.DataFrame(list(kpis_v["balance_agee"].items()), columns=["Tranche", "Montant (DZD)"])
                    st.bar_chart(df_balance.set_index("Tranche"), horizontal=True)
                with col_g2:
                    st.markdown("**Top Clients**")
                    if not kpis_v["top_clients"].empty:
                        st.bar_chart(
                            kpis_v["top_clients"].set_index("client_id")["montant_ttc"],
                            horizontal=True)
                        st.caption("Top 10 des clients facturés, brut TTC, sur la période.")
                    else:
                        st.info("Aucun client facturé pendant la période.")

        # --- 4. ACHATS ---
    if active_panel == _DASHBOARD_PANELS[3]:
        with read_section("Achats"):
            st.subheader("Analyse des Achats & Fournisseurs", help=topic_help("dashboard.achats"))
            show_context_help(st, "dashboard.achats")
            st.caption("Retards globaux, indépendants de la période : commandes en attente ou partiellement réceptionnées, échéance antérieure à aujourd’hui.")
            c_deb_a, c_fin_a = st.columns(2)
            date_deb_a = c_deb_a.date_input("Date de début", _dashboard_today().replace(day=1), key="d_a", on_change=_mark_dashboards_activity, help=field_help("Date de début", module="dashboards"))
            date_fin_a = c_fin_a.date_input("Date de fin", _dashboard_today(), key="f_a", on_change=_mark_dashboards_activity, help=field_help("Date de fin", module="dashboards"))

            if date_deb_a <= date_fin_a:
                ts_deb_a, ts_fin_a = pd.Timestamp(date_deb_a), pd.Timestamp(date_fin_a) + pd.Timedelta(days=1, seconds=-1)
                kpis_a = get_kpis_achats(ts_deb_a, ts_fin_a)

                ca1, ca2 = st.columns(2)
                ca1.metric("Commandes d'achat saisies (DZD)",
                           f"{kpis_a['montant_total']:,.2f} DZD",
                           help="Montant des commandes datées de la période, "
                                "pas des achats facturés ni des marchandises reçues.")
                ca2.metric("Commandes en retard", str(kpis_a['commandes_retard']), delta="À relancer" if kpis_a['commandes_retard'] > 0 else "OK", delta_color="inverse")
                st.divider()

                col_ga1, col_ga2 = st.columns(2)
                with col_ga1:
                    st.markdown("**Concentration Fournisseurs**")
                    df_rep = kpis_a["repartition_fournisseurs"]
                    if not df_rep.empty:
                        st.bar_chart(df_rep.set_index("fournisseur_id")[df_rep.columns[1]], horizontal=True)
                with col_ga2:
                    st.markdown("**Évolution du prix d'achat en DZD / unité de stock**")
                    df_evo = kpis_a["evolution_prix"]
                    if not df_evo.empty:
                        matiere = st.selectbox(
                            "Matière achetée", options=sorted(df_evo["mp_id"].unique().tolist()),
                            key="dashboard_achat_matiere",
                            on_change=_mark_dashboards_activity,
                            help="Comparer uniquement les prix du même article.")
                        unite = st.selectbox(
                            "Unité de stock", options=sorted(
                                df_evo.loc[df_evo["mp_id"] == matiere, "unite_cond"].unique().tolist()),
                            key="dashboard_achat_unite",
                            on_change=_mark_dashboards_activity,
                            help="Ne pas comparer des prix exprimés dans des unités différentes.")
                        selection = df_evo.loc[
                            (df_evo["mp_id"] == matiere) & (df_evo["unite_cond"] == unite)]
                        if not selection.empty:
                            st.line_chart(
                                selection.sort_values("date_obj").set_index("date_obj")[
                                    "prix_unitaire_dzd"],
                                use_container_width=True)
                            st.caption("Prix unitaire d'achat converti en DZD au taux de "
                                       "la commande ; non corrigé de l'inflation.")
                    else:
                        st.info("Historique des prix non comparable : aucune ligne "
                                "sur la période ou devise/unité de stock non vérifiable.")

        # --- 5. STOCKS ---
    if active_panel == _DASHBOARD_PANELS[4]:
        with read_section("Stocks"):
            st.subheader("Analyse Financière des Stocks", help=topic_help("dashboard.stocks"))
            show_context_help(st, "dashboard.stocks")
            jours = st.slider("Fenêtre d'alerte péremption (Jours)", 7, 120, 30, 7, on_change=_mark_dashboards_activity, help=field_help("Fenêtre d'alerte péremption (Jours)", module="dashboards"))
            kpis_s = get_kpis_stocks(jours_alerte_peremption=jours)

            if kpis_s.get("lots_sans_date", 0):
                st.warning(f"{kpis_s['lots_sans_date']} lot(s) avec stock sans date de péremption : risque non évalué.")
            if kpis_s.get("seuils_stock_absents", 0):
                st.warning(f"{kpis_s['seuils_stock_absents']} matière(s) en stock sans seuil minimum : alerte de rupture non évaluable pour ces références.")
            cs1, cs2, cs3, cs4 = st.columns(4)
            cs1.metric("Valeur du stock (estimation)", f"{kpis_s['valeur_totale']:,.2f} DZD")
            cs2.metric("Matières sous seuil connu", str(kpis_s["sous_seuil"]))
            cs3.metric("Lots déjà périmés", str(kpis_s["lots_perimes"]))
            cs4.metric(f"Lots à échéance (≤ {jours}j)", str(kpis_s["lots_a_echeance"]))
            st.caption("Le total des lots à risque exclut les lots sans date de "
                       "péremption, affichés dans l'alerte. Les seuils manquants "
                       "ne sont jamais considérés comme des seuils à zéro.")
            st.divider()

            c_st1, c_st2 = st.columns(2)
            with c_st1:
                st.markdown("**Répartition de la Valeur**")
                st.bar_chart(pd.DataFrame([{"Catégorie": "MP", "Valeur": kpis_s['valeur_mp']}, {"Catégorie": "PF", "Valeur": kpis_s['valeur_pf']}]).set_index("Catégorie"))
            with c_st2:
                st.markdown("**Détail des lots à risque**")
                st.dataframe(kpis_s["lots_expirants"], use_container_width=True, hide_index=True) if not kpis_s["lots_expirants"].empty else st.info("Aucun lot daté dans la fenêtre d’alerte.")

        # --- 6. PRODUCTION ---
    if active_panel == _DASHBOARD_PANELS[5]:
        with read_section("Production"):
            st.subheader("Performance de Production", help=topic_help("dashboard.production"))
            show_context_help(st, "dashboard.production")
            c_deb_p, c_fin_p = st.columns(2)
            date_deb_p = c_deb_p.date_input("Date de début", _dashboard_today().replace(day=1), key="d_p", on_change=_mark_dashboards_activity, help=field_help("Date de début", module="dashboards"))
            date_fin_p = c_fin_p.date_input("Date de fin", _dashboard_today(), key="f_p", on_change=_mark_dashboards_activity, help=field_help("Date de fin", module="dashboards"))

            if date_deb_p <= date_fin_p:
                ts_deb_p, ts_fin_p = pd.Timestamp(date_deb_p), pd.Timestamp(date_fin_p) + pd.Timedelta(days=1, seconds=-1)
                kpis_p = get_kpis_production(ts_deb_p, ts_fin_p)

                st.caption("OF de la cohorte planifiée dans la période (statut actuel). "
                           "CQ datés dans la période, sur un périmètre distinct ; "
                           "ce n'est pas un taux de rebut en kilogrammes, un taux OTIF "
                           "ni un TRS/OEE. Aucune cible de rejet n'est présumée.")
                cp1, cp2, cp3, cp4 = st.columns(4)
                cp1.metric("OF planifiés (cohorte)", str(kpis_p["total_ofs"]))
                cp2.metric("OF terminés dans cette cohorte", str(kpis_p["of_termines"]))
                cp3.metric("Taux d'achèvement de la cohorte",
                           _rate_or_na(kpis_p["taux_cloture"], kpis_p["total_ofs"]))
                cp4.metric(f"Rejets CQ / {kpis_p['nb_controles']} contrôles",
                           _rate_or_na(kpis_p["taux_rejet"], kpis_p["nb_controles"]))
                st.divider()
                st.markdown("**OF par date de planification**")
                if not kpis_p["evolution_of"].empty:
                    st.bar_chart(kpis_p["evolution_of"].set_index("Date"))
                else:
                    st.info("Aucun OF planifié dans la période.")
                st.markdown("**Répartition des OF selon leur statut actuel**")
                if not kpis_p["repartition_statut"].empty:
                    st.bar_chart(kpis_p["repartition_statut"].set_index("Statut"),
                                 horizontal=True)

        # --- 7. CRM ---
    if active_panel == _DASHBOARD_PANELS[6]:
        with read_section("CRM"):
            st.subheader("Performance Commerciale & Pipeline", help=topic_help("dashboard.crm"))
            show_context_help(st, "dashboard.crm")
            st.caption("Pipeline ouvert global. Conversion et valeurs gagnées : opportunités créées dans la période, selon leur statut actuel ; ce ne sont pas des ventes facturées ni des clôtures datées.")
            c_deb_c, c_fin_c = st.columns(2)
            date_deb_c = c_deb_c.date_input("Date de début", _dashboard_today().replace(day=1), key="d_c", on_change=_mark_dashboards_activity, help=field_help("Date de début", module="dashboards"))
            date_fin_c = c_fin_c.date_input("Date de fin", _dashboard_today(), key="f_c", on_change=_mark_dashboards_activity, help=field_help("Date de fin", module="dashboards"))

            if date_deb_c <= date_fin_c:
                ts_deb_c, ts_fin_c = pd.Timestamp(date_deb_c), pd.Timestamp(date_fin_c) + pd.Timedelta(days=1, seconds=-1)
                kpis_c = get_kpis_crm(ts_deb_c, ts_fin_c)

                cc1, cc2 = st.columns(2)
                cc1.metric("Pipeline Pondéré (En cours)", f"{kpis_c['pipeline_pondere']:,.2f} DZD", help="Valeur estimée * Probabilité des opportunités non clôturées.")
                cc2.metric(
                    "Conversion des opportunités clôturées",
                    _rate_or_na(kpis_c["taux_conversion"], kpis_c["nb_affaires_closes"]),
                    help="Gagnées / (gagnées + perdues), uniquement parmi les "
                         "opportunités créées sur la période et clôturées à date. "
                         "N/D en l'absence d'affaires closes.")
                st.divider()

                st.markdown("**Valeur estimée des opportunités gagnées par commercial**")
                if not kpis_c["performance_commerciaux"].empty:
                    st.bar_chart(kpis_c["performance_commerciaux"].set_index("Commercial"),
                                 horizontal=True)
                else:
                    st.info("Aucune opportunité actuellement gagnée parmi celles créées dans la période.")

        # --- 8. RH ---
    if active_panel == _DASHBOARD_PANELS[7]:
        with read_section("RH"):
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
    if active_panel == _DASHBOARD_PANELS[8]:
        with read_section("Finance"):
            st.subheader("Flux de Trésorerie & Rapprochement", help=topic_help("dashboard.finance"))
            show_context_help(st, "dashboard.finance")
            c_deb_f, c_fin_f = st.columns(2)
            date_deb_f = c_deb_f.date_input("Date de début", _dashboard_today().replace(day=1), key="d_f", on_change=_mark_dashboards_activity, help=field_help("Date de début", module="dashboards"))
            date_fin_f = c_fin_f.date_input("Date de fin", _dashboard_today(), key="f_f", on_change=_mark_dashboards_activity, help=field_help("Date de fin", module="dashboards"))

            if date_deb_f <= date_fin_f:
                ts_deb_f, ts_fin_f = pd.Timestamp(date_deb_f), pd.Timestamp(date_fin_f) + pd.Timedelta(days=1, seconds=-1)
                kpis_f = get_kpis_finance(ts_deb_f, ts_fin_f)

                cf1, cf2, cf3, cf4 = st.columns(4)
                cf1.metric("Encaissements validés", f"{kpis_f['flux_entrants']:,.2f} DZD")
                cf2.metric("Décaissements validés", f"{kpis_f['flux_sortants']:,.2f} DZD")
                cf3.metric("Flux net de période", f"{kpis_f['flux_net']:,.2f} DZD")
                cf4.metric("Taux d'affectation des encaissements",
                           _rate_or_na(kpis_f["taux_lettrage"], kpis_f["flux_entrants"]),
                           help="Montant affecté / total des encaissements validés "
                                "sur la période. Ce taux n'est pas un rapprochement bancaire.")
                st.caption(f"Encaissements non affectés aux factures sur la période : "
                           f"{kpis_f['encaissements_non_alloues']:,.2f} DZD.")
                st.markdown("**Évolution journalière des flux validés (DZD)**")
                if not kpis_f["evolution_flux"].empty:
                    st.line_chart(kpis_f["evolution_flux"].set_index("Date"),
                                  use_container_width=True)
                else:
                    st.info("Aucun règlement validé dans la période ; aucune courbe.")
                st.divider()
                st.markdown("**Soldes indicatifs Banque/Caisse à ce jour**")
                st.caption("Soldes initiaux + règlements VALIDE jusqu’à aujourd’hui, indépendants du filtre des flux. Comptes tiers exclus ; hors autres écritures et rapprochement bancaire. Les soldes initiaux ne sont pas datés dans le référentiel.")
                if not kpis_f["repartition_comptes"].empty:
                    df_pie = kpis_f["repartition_comptes"].assign(compte=lambda df: df["compte_id"].astype(str) + " — " + df["nom_compte"].astype(str)).set_index("compte")["solde"]
                    st.bar_chart(df_pie, horizontal=True)
                else:
                    st.info("Aucun compte financier configuré.")

    # OPT-04 : diagnostic local au rendu et réservé au profil administrateur.
    # Pas d'identifiant, pas de table, pas de requête SQL ni de secret exporté.
    # Les durées transport, autorisation et création de client se chevauchent.
    if str(user_role or "").strip().upper() in {"ADMIN", "ADMINISTRATEUR", "SUPERADMIN"}:
        metrics = query_metrics_snapshot()
        if metrics is not None:
            with st.expander("Diagnostic technique des lectures (ce rendu)"):
                st.caption(
                    f"Pages Supabase : {int(metrics['selects'])} | "
                    f"Contrôles d'accès : {int(metrics['checks'])} | "
                    f"Clients créés : {int(metrics['clients'])} | "
                    f"Lectures réutilisées : {int(metrics['cache_hits'])}"
                )
                st.caption(
                    f"Durée cumulée des lectures : {metrics['select_ms']:.1f} ms | "
                    f"Contrôles d'accès : {metrics['check_ms']:.1f} ms | "
                    f"Création de clients : {metrics['client_ms']:.1f} ms. "
                    "Durées chevauchantes, non additives ; "
                    "ne mesurent pas le rendu complet du navigateur."
                )
