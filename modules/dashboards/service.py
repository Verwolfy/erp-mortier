"""
Logique métier du module Dashboards.
Agrège les données pour les indicateurs clés (KPIs) et graphiques.
Interroge directement Supabase (SQL) via des filtres de dates pour des performances maximales.
"""
import pandas as pd
from datetime import timedelta
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy

# Cache éphémère par rendu, jamais partagé entre sessions utilisateurs.
# Il stocke des lignes brutes, puis retourne des DataFrame indépendants.
_DASHBOARD_READS: ContextVar[dict | None] = ContextVar(
    "nextgen_dashboard_reads", default=None
)
_DASHBOARD_DEMO: ContextVar[dict | None] = ContextVar(
    "nextgen_dashboard_demo", default=None
)


@contextmanager
def dashboard_read_scope(*, demo_rows: dict | None = None):
    """Isole chaque rendu et interdit tout repli vers Supabase en mode démo."""
    if demo_rows is not None:
        if not isinstance(demo_rows, dict) or not all(
                isinstance(name, str) and isinstance(rows, list)
                and all(isinstance(row, dict) for row in rows)
                for name, rows in demo_rows.items()):
            raise ValueError("Jeu de démonstration invalide")
    token = _DASHBOARD_READS.set({})
    demo_token = _DASHBOARD_DEMO.set(deepcopy(demo_rows))
    try:
        yield
    finally:
        _DASHBOARD_DEMO.reset(demo_token)
        _DASHBOARD_READS.reset(token)

from core.strict_reads import (fetch_data_strict as fetch_data,
                               fetch_data_by_date_range_strict as fetch_data_by_date_range)
from core.utils import get_local_now
from core.indicateurs_factures import (validated_documents, in_period, client_invoices,
                                      open_receivables, ageing_balance, numeric_values, dates)
from core.strict_reads import DataReadError
from core.indicateurs_stocks import stock_value, below_threshold, expiry_alerts, threshold_status
from core.indicateurs_tresorerie import validated_payments, cash_balances
from core.indicateurs_charges import payroll_net_for_period, supplier_operating_payments

def charger_donnees(table_name: str) -> pd.DataFrame:
    """Lecture stricte partagée pour un rendu, sans cache inter-utilisateur.

    Les contrôles de permission continuent de s'exécuter au premier accès,
    et chaque KPI reçoit sa propre copie des données.
    """
    current = _DASHBOARD_READS.get()
    demo = _DASHBOARD_DEMO.get()
    if demo is not None:
        if table_name not in demo:
            raise DataReadError("Table du scénario démo absente ; aucune lecture réelle autorisée")
        return pd.DataFrame(deepcopy(demo[table_name]))
    if current is None:
        return pd.DataFrame(fetch_data(table_name))
    if table_name not in current:
        current[table_name] = fetch_data(table_name)
    return pd.DataFrame(current[table_name]).copy(deep=True)


def _lire_periode(table_name: str, date_column: str,
                  start_date: str, end_date: str) -> pd.DataFrame:
    """Même source par rendu : DEMO 100% local OU requête bornée réelle."""
    demo = _DASHBOARD_DEMO.get()
    if demo is None:
        return pd.DataFrame(fetch_data_by_date_range(
            table_name, date_column, start_date, end_date))
    if table_name not in demo:
        raise DataReadError("Source de démonstration absente")
    frame = pd.DataFrame(deepcopy(demo[table_name]))
    if frame.empty:
        return frame
    if date_column not in frame:
        raise DataReadError("Date de scénario manquante")
    # La même validation stricte qu'en réel est appliquée, y compris
    # aux dates impossibles et aux lignes hors période.
    chronology = dates(frame, date_column)
    return frame.loc[chronology.between(
        pd.Timestamp(start_date), pd.Timestamp(end_date))].copy()


# Un préfixe DEMO/SIM est un indice de données d'exercice, jamais une
# qualification comptable automatique ni une autorisation de suppression.
_PROVENANCE_SOURCES = (
    ("factures", "facture_id", "Factures"),
    ("reglements", "reglement_id", "Règlements"),
    ("ordres_fabrication", "of_id", "OF"),
    ("commandes_achats", "commande_achat_id", "Commandes achats"),
    ("pipeline", "opportunite_id", "CRM"),
    ("employes", "employe_id", "RH"),
)


def get_dashboard_data_provenance() -> dict:
    """Diagnostic agrégé, lecture seule, sur les tables déjà nécessaires aux KPI.

    Une donnée marquée par un préfixe n'est PAS exclue des KPI : la
    qualification métier est indépendante de ce simple indice lexical.
    Toute lecture incomplète doit échouer explicitement.
    """
    sections = []
    total_marked = 0
    for table, identifier, display in _PROVENANCE_SOURCES:
        frame = charger_donnees(table)
        if frame.empty:
            sections.append({"Source": display, "Références DEMO/SIM": 0, "Total": 0})
            continue
        if identifier not in frame or not frame[identifier].map(
                lambda val: isinstance(val, str) and bool(val.strip())).all():
            raise DataReadError("Identifiants de provenance non qualifiés")
        labels = frame[identifier].str.strip().str.upper()
        marked = int(labels.str.startswith(("DEMO", "SIM")).sum())
        total_marked += marked
        sections.append({"Source": display, "Références DEMO/SIM": marked,
                         "Total": len(frame)})
    return {"marked": total_marked, "sources": sections}


def get_kpis_direction() -> dict:
    now = get_local_now()
    documents = validated_documents(charger_donnees("factures"))
    invoices = client_invoices(in_period(documents, now.replace(day=1), now))
    ca_mois = invoices["montant_ht"].sum()
    receivables = open_receivables(documents, now)
    impayes_30j = receivables.loc[receivables["retard_jours"] > 30, "reste_a_payer"].sum()

    # 2. Trésorerie
    df_cpt = charger_donnees("comptes")
    df_reg = charger_donnees("reglements")
    treso_dispo = cash_balances(df_cpt, validated_payments(df_reg), now)['solde'].sum()

    # 3. Alertes Stock (Matières Premières sous seuil)
    df_stock_mp = charger_donnees("stock_actuel")
    df_ref_mp = charger_donnees("matieres_premieres")
    alertes_stock, seuils_absents = threshold_status(df_stock_mp, df_ref_mp)

    return {"ca_mois": ca_mois, "tresorerie": treso_dispo,
            "impayes_30j": impayes_30j, "alertes_stock": alertes_stock,
            "seuils_stock_absents": seuils_absents}

def get_kpis_pnl(date_debut: pd.Timestamp, date_fin: pd.Timestamp) -> dict:
    """Calcule le Compte de Résultat (P&L) de manière optimisée."""
    start_str = date_debut.strftime("%Y-%m-%d")
    end_str = date_fin.strftime("%Y-%m-%d")

    # Fetch uniquement sur la période
    df_fac_periode = _lire_periode("factures", "date", start_str, end_str)
    df_reg_periode = _lire_periode("reglements", "date_reglement", start_str, end_str)

    df_frn = charger_donnees("fournisseurs")
    df_paie = charger_donnees("fiches_de_paie") # Filtrage mensuel contrôlé ci-dessous

    # Ne pas charger les lignes/coûts si aucune facture client validée
    # n'entre dans la période. Les charges restent prises en compte.
    documents = validated_documents(df_fac_periode)
    invoices = client_invoices(documents)
    ca_ht = invoices["montant_ht"].sum()
    cogs = 0.0
    if not invoices.empty:
        df_lignes_fac = charger_donnees("lignes_facture")
        df_pf = charger_donnees("stock_actuel_pf")
        if df_lignes_fac.empty or not {"facture_id", "sku_id", "quantite"}.issubset(df_lignes_fac):
            raise DataReadError("Lignes de facture indisponibles pour le coût")
        lignes_periode = df_lignes_fac[df_lignes_fac["facture_id"].isin(invoices["facture_id"])].copy()
        if set(invoices["facture_id"]) != set(lignes_periode["facture_id"]):
            raise DataReadError("Facture sans lignes de coût")
        if df_pf.empty or not {"sku_id", "cout_revient"}.issubset(df_pf):
            raise DataReadError("Coûts des produits indisponibles")
        costs = df_pf[df_pf["sku_id"].isin(lignes_periode["sku_id"])]
        if costs["sku_id"].duplicated().any():
            raise DataReadError("Coût produit ambigu")
        merged = lignes_periode.merge(costs[["sku_id", "cout_revient"]], on="sku_id", how="left")
        quantities = numeric_values(merged, "quantite")
        unit_costs = numeric_values(merged, "cout_revient")
        if (quantities <= 0).any() or (unit_costs < 0).any():
            raise DataReadError("Quantité ou coût non exploitable")
        cogs = (quantities * unit_costs).sum()

    marge_brute = ca_ht - cogs

    # Décaissements et nets enregistrés : indicateurs de gestion, pas charges SCF.
    opex_fournisseurs = supplier_operating_payments(df_reg_periode, df_frn)
    opex_salaires = payroll_net_for_period(df_paie, date_debut, date_fin)

    total_opex = opex_fournisseurs + opex_salaires
    ebitda = marge_brute - total_opex

    return {
        "ca_ht": ca_ht,
        "cogs": cogs,
        "marge_brute": marge_brute,
        "taux_marge_brute": (marge_brute / ca_ht * 100) if ca_ht > 0 else 0.0,
        "opex_fournisseurs": opex_fournisseurs,
        "opex_salaires": opex_salaires,
        "ebitda": ebitda,
        "taux_ebitda": (ebitda / ca_ht * 100) if ca_ht > 0 else 0.0
    }

def get_kpis_ventes(date_debut: pd.Timestamp, date_fin: pd.Timestamp) -> dict:
    # Une seule lecture : la balance reste globale même sans ventes sur la période.
    documents = validated_documents(charger_donnees("factures"))
    period = in_period(documents, date_debut, date_fin)
    invoices = client_invoices(period)
    credits = period.loc[period["type_facture"] == "FactureAvoir"]
    ca_ttc = invoices["montant_ttc"].sum()
    count = len(invoices)
    balance = ageing_balance(open_receivables(documents, get_local_now()))
    top_clients = (invoices.groupby("client_id")["montant_ttc"].sum().reset_index()
                   .sort_values(by="montant_ttc", ascending=False).head(10))
    # Évolution de la facturation BRUTE validée (sans avoirs), dans la
    # période sélectionnée. Aucune donnée simulée ni lecture supplémentaire.
    if invoices.empty:
        evolution = pd.DataFrame(columns=["Date", "Facturation HT (DZD)"])
    else:
        evolution = (invoices.groupby("date_obj", as_index=False)["montant_ht"]
                     .sum()
                     .rename(columns={"date_obj": "Date",
                                      "montant_ht": "Facturation HT (DZD)"})
                     .sort_values("Date"))
    return {
        "ca_ht": invoices["montant_ht"].sum(), "ca_ttc": ca_ttc,
        "timbre_fiscal": invoices["montant_timbre"].sum(),
        "panier_moyen": ca_ttc / count if count else 0.0,
        "taux_avoirs": credits["montant_ttc"].abs().sum() / ca_ttc * 100 if ca_ttc > 0 else 0.0,
        "nb_factures": count, "balance_agee": balance, "top_clients": top_clients,
        "evolution_facturation": evolution,
    }

def get_kpis_achats(date_debut: pd.Timestamp, date_fin: pd.Timestamp) -> dict:
    start_str = date_debut.strftime("%Y-%m-%d")
    end_str = date_fin.strftime("%Y-%m-%d")

    df_cmd = charger_donnees("commandes_achats") # Besoin global pour commandes en retard
    df_periode = _lire_periode("commandes_achats", "date_commande", start_str, end_str)
    # Les lignes ne servent qu'à l'évolution des prix sur une période non vide.
    df_lignes = charger_donnees("lignes_achats") if not df_periode.empty else pd.DataFrame()

    montant_total = 0.0
    col_montant = "montant_total_local" if "montant_total_local" in df_periode.columns else "montant_total"
    if not df_periode.empty:
        df_periode[col_montant] = numeric_values(df_periode, col_montant)
        montant_total = df_periode[col_montant].sum()

    # Retards globaux
    now = pd.Timestamp(get_local_now()).tz_localize(None).normalize()
    commandes_retard = 0
    if not df_cmd.empty:
        if 'statut' not in df_cmd or not df_cmd['statut'].isin([
                'EN_ATTENTE','PARTIELLEMENT_RECEPTIONNE','RECEPTIONNE','TERMINE','ANNULE']).all():
            raise DataReadError('Statut de commande non reconnu')
        pending = df_cmd.loc[df_cmd['statut'].isin(['EN_ATTENTE','PARTIELLEMENT_RECEPTIONNE'])]
        if not pending.empty:
            commandes_retard = int((dates(pending, 'date_voulue') < now).sum())

    repartition = df_periode.groupby("fournisseur_id")[col_montant].sum().reset_index().sort_values(by=col_montant, ascending=False) if not df_periode.empty and "fournisseur_id" in df_periode.columns else pd.DataFrame()

    # Comparer uniquement des prix exprimés dans une MÊME unité de stock
    # et une MÊME devise (DZD). Les prix en devises sont convertis au taux
    # confirmé sur la commande ; ne pas tracer des montants non comparables.
    evolution_prix = pd.DataFrame()
    needed_header = {"commande_achat_id", "date_commande", "devise", "taux_change"}
    needed_lines = {"commande_achat_id", "mp_id", "unite_cond", "prix_unitaire"}
    if not df_periode.empty and not df_lignes.empty and needed_header.issubset(df_periode.columns) and needed_lines.issubset(df_lignes.columns):
        df_periode["date_obj"] = dates(df_periode, "date_commande")
        df_merge = pd.merge(
            df_lignes,
            df_periode[["commande_achat_id", "date_obj", "devise", "taux_change"]],
            on="commande_achat_id", how="inner")
        if not df_merge.empty:
            price = numeric_values(df_merge, "prix_unitaire")
            fx = numeric_values(df_merge, "taux_change")
            if (price < 0).any() or (fx <= 0).any():
                raise DataReadError("Prix d'achat ou taux de change non exploitable")
            if (df_merge["mp_id"].isna().any() or df_merge["unite_cond"].isna().any()
                    or df_merge["unite_cond"].astype(str).str.strip().eq("").any()):
                raise DataReadError("Unité d'achat non qualifiée")
            if not df_merge["devise"].map(lambda v: isinstance(v, str) and bool(v.strip())).all():
                raise DataReadError("Devise d'achat non qualifiée")
            df_merge["prix_unitaire_dzd"] = price * fx
            evolution_prix = df_merge[["date_obj", "mp_id", "unite_cond",
                                      "prix_unitaire_dzd"]].copy()

    return {"montant_total": montant_total, "commandes_retard": commandes_retard, "repartition_fournisseurs": repartition, "evolution_prix": evolution_prix}

def get_kpis_stocks(jours_alerte_peremption: int = 30) -> dict:
    # Le stock actuel n'a pas besoin de filtre temporel
    df_stock_mp = charger_donnees("stock_actuel")
    df_stock_pf = charger_donnees("stock_actuel_pf")
    df_lots = charger_donnees("lots")
    df_ref_mp = charger_donnees("matieres_premieres")

    valeur_mp = stock_value(df_stock_mp, "cmp_actuel")
    valeur_pf = stock_value(df_stock_pf, "cout_revient")
    sous_seuil, seuils_absents = threshold_status(df_stock_mp, df_ref_mp)
    today = get_local_now()
    lots_expirants, lots_sans_date = expiry_alerts(df_lots, today, jours_alerte_peremption)
    # "Périmé" = date strictement passée ; échéance aujourd'hui dans
    # "à échéance", sans fausse valorisation des lots ni approximation.
    lots_perimes = 0
    if not lots_expirants.empty:
        expiry_dates = dates(lots_expirants, "date_peremption")
        lots_perimes = int((expiry_dates < pd.Timestamp(today).tz_localize(None).normalize()).sum())
    return {"valeur_mp": valeur_mp, "valeur_pf": valeur_pf,
            "valeur_totale": valeur_mp + valeur_pf, "sous_seuil": sous_seuil,
            "seuils_stock_absents": seuils_absents,
            "lots_expirants": lots_expirants, "lots_sans_date": lots_sans_date,
            "lots_perimes": lots_perimes,
            "lots_a_echeance": len(lots_expirants) - lots_perimes}

def get_kpis_production(date_debut: pd.Timestamp, date_fin: pd.Timestamp) -> dict:
    start_str = date_debut.strftime("%Y-%m-%d")
    end_str = date_fin.strftime("%Y-%m-%d")

    df_periode = _lire_periode("ordres_fabrication", "date_planification", start_str, end_str)
    df_cq = _lire_periode("controle_qualite", "date", start_str, end_str)

    # Cohorte d'OF datée par PLANIFICATION, pas par clôture : leur état
    # actuel ne constitue pas un taux de ponctualité ni un OEE.
    total_ofs = len(df_periode)
    repartition = pd.DataFrame(columns=["Statut", "Volume"])
    evolution_of = pd.DataFrame(columns=["Date", "OF planifiés"])
    of_termines = 0
    if not df_periode.empty:
        if "statut" not in df_periode or not df_periode["statut"].isin(
                ["PLANIFIE", "EN_COURS", "CONTROLE_QUALITE", "TERMINE", "REJETE"]).all():
            raise DataReadError("Statut d'OF manquant ou inconnu")
        repartition = df_periode["statut"].value_counts().reset_index()
        repartition.columns = ["Statut", "Volume"]
        of_termines = int((df_periode["statut"] == "TERMINE").sum())
        by_day = dates(df_periode, "date_planification")
        evolution_of = (pd.DataFrame({"Date": by_day})
                        .groupby("Date", as_index=False).size()
                        .rename(columns={"size": "OF planifiés"}).sort_values("Date"))

    # CQ filtré par DATE DU CONTRÔLE : son dénominateur n'est pas le nombre
    # d'OF planifiés ci-dessus. Afficher N/D si aucun contrôle n'existe.
    nb_controles, nb_rejets = len(df_cq), 0
    if nb_controles:
        if "conforme" not in df_cq or df_cq["conforme"].isna().any():
            raise DataReadError("Conformité CQ indisponible")
        statuses = df_cq["conforme"].astype(str).str.strip().str.upper()
        if not statuses.isin(["OUI", "TRUE", "CONFORME",
                              "NON", "FALSE", "REJETE"]).all():
            raise DataReadError("Conformité CQ inconnue")
        nb_rejets = int(statuses.isin(["NON", "FALSE", "REJETE"]).sum())
    taux_rejet = nb_rejets / nb_controles * 100 if nb_controles else 0.0

    return {"total_ofs": total_ofs, "repartition_statut": repartition,
            "taux_rejet": taux_rejet, "nb_controles": nb_controles,
            "nb_rejets": nb_rejets, "of_termines": of_termines,
            "taux_cloture": of_termines / total_ofs * 100 if total_ofs else 0.0,
            "evolution_of": evolution_of}

def get_kpis_crm(date_debut: pd.Timestamp, date_fin: pd.Timestamp) -> dict:
    frame = charger_donnees("pipeline")
    empty = {"pipeline_pondere": 0.0, "taux_conversion": 0.0,
             "nb_affaires_closes": 0, "performance_commerciaux": pd.DataFrame()}
    if frame.empty:
        return empty
    # Les libellés du formulaire sont conservés en base ; anciens codes acceptés.
    aliases = {"Nouveau":"OPEN", "Contacté":"OPEN", "En Négociation":"OPEN",
               "Gagné":"WON", "Perdu":"LOST", "NOUVELLE":"OPEN", "EN_COURS":"OPEN",
               "QUALIFICATION":"OPEN", "PROPOSITION":"OPEN", "GAGNEE":"WON", "PERDUE":"LOST"}
    if 'statut' not in frame or not frame['statut'].isin(aliases).all():
        raise DataReadError('Statut CRM non reconnu')
    frame = frame.copy()
    frame['state'] = frame['statut'].map(aliases)
    frame['value'] = numeric_values(frame, 'valeur_estimee')
    frame['probability'] = numeric_values(frame, 'probabilite_pct')
    if (frame['value'] < 0).any() or not frame['probability'].between(0,100).all():
        raise DataReadError('Valeur ou probabilité CRM invalide')
    created = dates(frame, 'date_creation')
    period = frame.loc[created.between(pd.Timestamp(date_debut).tz_localize(None).normalize(),
                                       pd.Timestamp(date_fin).tz_localize(None).normalize())]
    opened = frame.loc[frame['state']=='OPEN']
    closed = period.loc[period['state'].isin(['WON','LOST'])]
    won = closed.loc[closed['state']=='WON'].copy()
    perf = pd.DataFrame()
    if not won.empty:
        if 'commercial_id' not in won:
            raise DataReadError('Commercial absent')
        won['commercial_id'] = won['commercial_id'].fillna('').astype(str).str.strip().replace('', 'Non attribué')
        perf = won.groupby('commercial_id')['value'].sum().reset_index()
        perf.columns = ['Commercial', 'Valeur estimée gagnée']
        perf = perf.sort_values('Valeur estimée gagnée', ascending=False)
    return {"pipeline_pondere": (opened['value'] * opened['probability'] / 100).sum(),
            "taux_conversion": len(won) / len(closed) * 100 if len(closed) else 0.0,
            "nb_affaires_closes": len(closed),
            "performance_commerciaux": perf}

def get_kpis_rh(date_debut: pd.Timestamp, date_fin: pd.Timestamp) -> dict:
    df_emp = charger_donnees("employes")
    df_conges = charger_donnees("demandes_conges")

    effectif_actif = 0
    repart_service = pd.DataFrame()

    if not df_emp.empty:
        if 'actif' not in df_emp or not df_emp['actif'].isin(['OUI','NON']).all():
            raise DataReadError('Indicateur actif RH absent ou invalide')
        df_actifs = df_emp.loc[df_emp['actif']=='OUI'].copy()
        effectif_actif = len(df_actifs)
        if not df_actifs.empty:
            if 'service' not in df_actifs:
                raise DataReadError('Champ service absent')
            labels = df_actifs['service'].fillna('').astype(str).str.strip().replace('', 'Non renseigné')
            repart_service = labels.value_counts().rename_axis('Service').reset_index(name='Effectif')

    conges_attente = 0
    if not df_conges.empty:
        if "statut" not in df_conges or df_conges["statut"].isna().any():
            raise DataReadError("Statut de congé absent")
        conges_attente = len(df_conges[df_conges["statut"] == "EN_ATTENTE"])

    return {"effectif_actif": effectif_actif, "repartition_service": repart_service, "conges_attente": conges_attente}

def get_kpis_finance(date_debut: pd.Timestamp, date_fin: pd.Timestamp) -> dict:
    accounts = charger_donnees("comptes")
    payments = validated_payments(charger_donnees("reglements"))
    balances = cash_balances(accounts, payments, get_local_now())
    period = payments.loc[payments['date_obj'].between(
        pd.Timestamp(date_debut).tz_localize(None).normalize(),
        pd.Timestamp(date_fin).tz_localize(None).normalize())]
    incoming = period.loc[period['type_flux'] == 'ENCAISSEMENT']
    total_in = incoming['montant_total'].sum()
    total_out = period.loc[period['type_flux'] == 'DECAISSEMENT', 'montant_total'].sum()
    allocated = incoming["montant_alloue"].sum()
    # Série réelle jour par jour, sans interpolation artificielle ni
    # comparaison de flux périodiques avec les soldes cumulés à aujourd'hui.
    flow = pd.DataFrame(columns=["Date", "Encaissements (DZD)", "Décaissements (DZD)"])
    if not period.empty:
        flow = (period.pivot_table(index="date_obj", columns="type_flux",
                                   values="montant_total", aggfunc="sum", fill_value=0)
                .rename(columns={"ENCAISSEMENT": "Encaissements (DZD)",
                                 "DECAISSEMENT": "Décaissements (DZD)"}))
        for column in ("Encaissements (DZD)", "Décaissements (DZD)"):
            if column not in flow:
                flow[column] = 0.0
        flow = (flow[["Encaissements (DZD)", "Décaissements (DZD)"]]
                .reset_index().rename(columns={"date_obj": "Date"}).sort_values("Date"))
    return {
        "repartition_comptes": balances, "flux_entrants": total_in,
        "flux_sortants": total_out, "flux_net": total_in - total_out,
        "encaissements_non_alloues": total_in - allocated,
        "taux_lettrage": allocated / total_in * 100 if total_in else 0.0,
        "evolution_flux": flow,
    }
