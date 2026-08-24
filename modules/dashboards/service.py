"""
Logique métier du module Dashboards.
Agrège les données pour les indicateurs clés (KPIs) et graphiques.
Interroge désormais directement Supabase (SQL) pour une fiabilité et des performances maximales.
"""
import pandas as pd
from datetime import timedelta
from core.db_service import fetch_data
from core.utils import get_local_now

def charger_donnees(table_name: str) -> pd.DataFrame:
    """Fonction utilitaire pour charger une table SQL sous forme de DataFrame sécurisé."""
    return pd.DataFrame(fetch_data(table_name))

def get_kpis_direction() -> dict:
    now = get_local_now()

    # 1. CA & Impayés
    df_fac = charger_donnees("factures")
    ca_mois = 0.0
    impayes_30j = 0.0

    if not df_fac.empty and "facture_id" in df_fac.columns:
        for col in ["montant_ht", "montant_ttc", "montant_paye"]:
            if col in df_fac.columns:
                df_fac[col] = pd.to_numeric(df_fac[col], errors="coerce").fillna(0)

        col_date = "date" if "date" in df_fac.columns else df_fac.columns[3]
        df_fac["date_obj"] = pd.to_datetime(df_fac[col_date], errors="coerce")

        mask_mois = (df_fac["date_obj"].dt.month == now.month) & (df_fac["date_obj"].dt.year == now.year)
        if "type_document" in df_fac.columns:
            mask_mois = mask_mois & (df_fac["type_document"] == "FactureClient")
        elif "type_facture" in df_fac.columns:
            mask_mois = mask_mois & (df_fac["type_facture"] == "FactureClient")

        ca_mois = df_fac[mask_mois]["montant_ht"].sum()

        limite_30j = pd.Timestamp(now - timedelta(days=30)).tz_localize(None)
        if "date_echeance" in df_fac.columns and "statut" in df_fac.columns:
            df_fac["date_echeance_obj"] = pd.to_datetime(df_fac["date_echeance"], errors="coerce").dt.tz_localize(None)
            mask_impayes = (df_fac["statut"].isin(["EN_ATTENTE", "PARTIELLE", "VALIDE", "BROUILLON"])) & (df_fac["date_echeance_obj"] < limite_30j)
            impayes_30j = (df_fac[mask_impayes]["montant_ttc"] - df_fac[mask_impayes]["montant_paye"]).sum()

    # 2. Trésorerie
    df_cpt = charger_donnees("comptes")
    df_reg = charger_donnees("reglements")
    treso_dispo = 0.0

    if not df_cpt.empty and "solde_initial" in df_cpt.columns:
        treso_dispo += pd.to_numeric(df_cpt["solde_initial"], errors="coerce").fillna(0).sum()

    if not df_reg.empty and "montant_total" in df_reg.columns and "type_flux" in df_reg.columns:
        df_reg["montant_total"] = pd.to_numeric(df_reg["montant_total"], errors="coerce").fillna(0)
        treso_dispo += df_reg[df_reg["type_flux"] == "ENCAISSEMENT"]["montant_total"].sum()
        treso_dispo -= df_reg[df_reg["type_flux"] == "DECAISSEMENT"]["montant_total"].sum()

    # 3. Alertes Stock
    df_stock_mp = charger_donnees("stock_actuel")
    df_ref_mp = charger_donnees("matieres_premieres")
    alertes_stock = 0

    if not df_stock_mp.empty and not df_ref_mp.empty and "mp_id" in df_stock_mp.columns:
        merged = pd.merge(df_stock_mp, df_ref_mp, on="mp_id", how="inner")
        if "quantite_disponible" in merged.columns and "stock_mini" in merged.columns:
            merged["qte"] = pd.to_numeric(merged["quantite_disponible"], errors="coerce").fillna(0)
            merged["mini"] = pd.to_numeric(merged["stock_mini"], errors="coerce").fillna(0)
            alertes_stock = len(merged[merged["qte"] < merged["mini"]])

    return {"ca_mois": ca_mois, "tresorerie": treso_dispo, "impayes_30j": impayes_30j, "alertes_stock": alertes_stock}

def get_kpis_ventes(date_debut: pd.Timestamp, date_fin: pd.Timestamp) -> dict:
    df_fac = charger_donnees("factures")
    if df_fac.empty or "facture_id" not in df_fac.columns:
        return {"ca_ht": 0.0, "ca_ttc": 0.0, "timbre_fiscal": 0.0, "panier_moyen": 0.0, "taux_avoirs": 0.0, "nb_factures": 0, "balance_agee": {}, "top_clients": pd.DataFrame()}

    for col in ["montant_ht", "montant_ttc", "montant_paye", "montant_timbre"]:
        if col in df_fac.columns:
            df_fac[col] = pd.to_numeric(df_fac[col], errors="coerce").fillna(0)

    col_date = "date" if "date" in df_fac.columns else df_fac.columns[3]
    df_fac["date_obj"] = pd.to_datetime(df_fac[col_date], errors="coerce").dt.tz_localize(None)

    mask_periode = (df_fac["date_obj"] >= date_debut) & (df_fac["date_obj"] <= date_fin)
    df_periode = df_fac[mask_periode].copy()

    type_col = "type_document" if "type_document" in df_fac.columns else "type_facture"
    if type_col not in df_periode.columns:
        df_periode[type_col] = "FactureClient"

    df_clients_purs = df_periode[df_periode[type_col] == "FactureClient"]
    df_avoirs = df_periode[df_periode[type_col] == "FactureAvoir"]

    ca_ttc = df_clients_purs["montant_ttc"].sum()
    nb_factures = len(df_clients_purs)

    df_fac["date_echeance_obj"] = pd.to_datetime(df_fac.get("date_echeance", df_fac["date_obj"]), errors="coerce").dt.tz_localize(None)

    if "statut" in df_fac.columns:
        mask_ouvertes = df_fac["statut"].isin(["EN_ATTENTE", "PARTIELLE", "VALIDE", "BROUILLON"])
    else:
        mask_ouvertes = pd.Series([False] * len(df_fac))

    df_ouvertes = df_fac[mask_ouvertes].copy()

    now = pd.Timestamp(get_local_now()).tz_localize(None)
    df_ouvertes["retard_jours"] = (now - df_ouvertes["date_echeance_obj"]).dt.days
    df_ouvertes["reste_a_payer"] = df_ouvertes["montant_ttc"] - df_ouvertes["montant_paye"]

    balance_agee = {
        "Non échu": df_ouvertes[df_ouvertes["retard_jours"] <= 0]["reste_a_payer"].sum(),
        "1 à 30 jours": df_ouvertes[(df_ouvertes["retard_jours"] > 0) & (df_ouvertes["retard_jours"] <= 30)]["reste_a_payer"].sum(),
        "31 à 60 jours": df_ouvertes[(df_ouvertes["retard_jours"] > 30) & (df_ouvertes["retard_jours"] <= 60)]["reste_a_payer"].sum(),
        "+ de 60 jrs": df_ouvertes[df_ouvertes["retard_jours"] > 60]["reste_a_payer"].sum(),
    }

    top_clients = df_clients_purs.groupby("client_id")["montant_ttc"].sum().reset_index().sort_values(by="montant_ttc", ascending=False).head(10) if not df_clients_purs.empty and "client_id" in df_clients_purs.columns else pd.DataFrame()

    return {
        "ca_ht": df_clients_purs["montant_ht"].sum(), "ca_ttc": ca_ttc,
        "timbre_fiscal": df_clients_purs["montant_timbre"].sum() if "montant_timbre" in df_clients_purs.columns else 0.0,
        "panier_moyen": ca_ttc / nb_factures if nb_factures > 0 else 0.0,
        "taux_avoirs": (df_avoirs["montant_ttc"].abs().sum() / ca_ttc * 100) if ca_ttc > 0 else 0.0,
        "nb_factures": nb_factures, "balance_agee": balance_agee, "top_clients": top_clients
    }

def get_kpis_achats(date_debut: pd.Timestamp, date_fin: pd.Timestamp) -> dict:
    df_cmd = charger_donnees("commandes_achats")
    df_lignes = charger_donnees("lignes_achats")

    if df_cmd.empty:
        return {"montant_total": 0.0, "commandes_retard": 0, "repartition_fournisseurs": pd.DataFrame(), "evolution_prix": pd.DataFrame()}

    col_montant = "montant_total_local" if "montant_total_local" in df_cmd.columns else "montant_total"
    if col_montant in df_cmd.columns:
        df_cmd[col_montant] = pd.to_numeric(df_cmd[col_montant], errors="coerce").fillna(0)

    col_date = "date_commande" if "date_commande" in df_cmd.columns else (df_cmd.columns[1] if len(df_cmd.columns) > 1 else df_cmd.columns[0])
    df_cmd["date_obj"] = pd.to_datetime(df_cmd[col_date], errors="coerce").dt.tz_localize(None)

    if "date_voulue" in df_cmd.columns:
        col_voulue = "date_voulue"
    elif "date_livraison_prevue" in df_cmd.columns:
        col_voulue = "date_livraison_prevue"
    else:
        col_voulue = col_date

    df_cmd["date_voulue_obj"] = pd.to_datetime(df_cmd[col_voulue], errors="coerce").dt.tz_localize(None)

    mask_periode = (df_cmd["date_obj"] >= date_debut) & (df_cmd["date_obj"] <= date_fin)
    df_periode = df_cmd[mask_periode].copy()
    montant_total = df_periode[col_montant].sum() if not df_periode.empty and col_montant in df_periode.columns else 0.0

    now = pd.Timestamp(get_local_now()).tz_localize(None)
    mask_retard = (df_cmd["date_voulue_obj"] < now)

    if "statut" in df_cmd.columns:
        mask_retard = mask_retard & (~df_cmd["statut"].isin(["RECEPTIONNE", "TERMINE", "ANNULE"]))

    repartition = df_periode.groupby("fournisseur_id")[col_montant].sum().reset_index().sort_values(by=col_montant, ascending=False) if not df_periode.empty and "fournisseur_id" in df_periode.columns else pd.DataFrame()

    evolution_prix = pd.DataFrame()
    if not df_lignes.empty and "commande_achat_id" in df_lignes.columns and "prix_unitaire" in df_lignes.columns:
        df_lignes["prix_unitaire"] = pd.to_numeric(df_lignes["prix_unitaire"], errors="coerce").fillna(0)
        if "commande_achat_id" in df_cmd.columns:
            df_merge = pd.merge(df_lignes, df_cmd[["commande_achat_id", "date_obj"]], on="commande_achat_id", how="inner")
            if not df_merge.empty:
                evolution_prix = df_merge[["date_obj", "mp_id", "prix_unitaire"]].dropna()

    return {"montant_total": montant_total, "commandes_retard": len(df_cmd[mask_retard]), "repartition_fournisseurs": repartition, "evolution_prix": evolution_prix}

def get_kpis_stocks(jours_alerte_peremption: int = 30) -> dict:
    df_stock = charger_donnees("stock_actuel")
    df_lots = charger_donnees("lots")
    df_ref_mp = charger_donnees("matieres_premieres")

    valeur_mp, valeur_pf, sous_seuil = 0.0, 0.0, 0
    lots_expirants = pd.DataFrame()

    if not df_stock.empty and "item_id" in df_stock.columns and "cmp_actuel" in df_stock.columns:
        if "quantite_disponible" in df_stock.columns:
            df_stock["qte"] = pd.to_numeric(df_stock["quantite_disponible"], errors="coerce").fillna(0)
        else:
            df_stock["qte"] = 0.0

        df_stock["cmp"] = pd.to_numeric(df_stock["cmp_actuel"], errors="coerce").fillna(0)
        df_stock["valeur"] = df_stock["qte"] * df_stock["cmp"]

        mask_mp = df_stock["item_id"].str.startswith("MP", na=False)
        mask_pf = df_stock["item_id"].str.startswith("SKU", na=False) | df_stock["item_id"].str.startswith("PF", na=False)

        valeur_mp = df_stock[mask_mp]["valeur"].sum()
        valeur_pf = df_stock[mask_pf]["valeur"].sum()

        if not df_ref_mp.empty and "mp_id" in df_ref_mp.columns:
            df_stock_mp = df_stock[mask_mp].copy()
            col_id = "mp_id" if "mp_id" in df_stock_mp.columns else "item_id"
            merged = pd.merge(df_stock_mp, df_ref_mp, left_on=col_id, right_on="mp_id", how="inner")
            if "stock_mini" in merged.columns:
                merged["mini"] = pd.to_numeric(merged["stock_mini"], errors="coerce").fillna(0)
                sous_seuil = len(merged[merged["qte"] < merged["mini"]])

    if not df_lots.empty and "date_peremption" in df_lots.columns:
        now = pd.Timestamp(get_local_now()).tz_localize(None)
        limite = now + timedelta(days=jours_alerte_peremption)
        df_lots["date_peremption_obj"] = pd.to_datetime(df_lots["date_peremption"], errors="coerce").dt.tz_localize(None)

        if "quantite_restante" in df_lots.columns:
            df_lots["qte_lot"] = pd.to_numeric(df_lots["quantite_restante"], errors="coerce").fillna(0)
        else:
            df_lots["qte_lot"] = 0.0

        mask_lots = (df_lots["qte_lot"] > 0) & (df_lots["date_peremption_obj"] >= now) & (df_lots["date_peremption_obj"] <= limite)

        # SÉCURISATION MAXIMALE : Ne sélectionner que les colonnes qui existent vraiment
        colonnes_ideales = ["lot_id", "item_id", "date_peremption", "quantite_restante"]
        cols_to_select = [col for col in colonnes_ideales if col in df_lots.columns]

        lots_expirants = df_lots[mask_lots][cols_to_select].copy()

    return {"valeur_mp": valeur_mp, "valeur_pf": valeur_pf, "valeur_totale": valeur_mp + valeur_pf, "sous_seuil": sous_seuil, "lots_expirants": lots_expirants}

def get_kpis_production(date_debut: pd.Timestamp, date_fin: pd.Timestamp) -> dict:
    df_of = charger_donnees("ordres_fabrication")
    df_cq = charger_donnees("controle_qualite")

    if df_of.empty:
        return {"total_ofs": 0, "repartition_statut": pd.DataFrame(), "taux_rejet": 0.0}

    col_date = "date_planification" if "date_planification" in df_of.columns else df_of.columns[6]
    df_of["date_obj"] = pd.to_datetime(df_of[col_date], errors="coerce").dt.tz_localize(None)
    mask_periode = (df_of["date_obj"] >= date_debut) & (df_of["date_obj"] <= date_fin)
    df_periode = df_of[mask_periode].copy()

    total_ofs = len(df_periode)
    repartition = pd.DataFrame()
    if total_ofs > 0 and "statut" in df_periode.columns:
        repartition = df_periode["statut"].value_counts().reset_index()
        repartition.columns = ["Statut", "Volume"]

    taux_rejet = 0.0
    if not df_cq.empty and "conforme" in df_cq.columns and "date_controle" in df_cq.columns:
        df_cq["date_obj"] = pd.to_datetime(df_cq["date_controle"], errors="coerce").dt.tz_localize(None)
        mask_cq = (df_cq["date_obj"] >= date_debut) & (df_cq["date_obj"] <= date_fin)
        df_cq_periode = df_cq[mask_cq]
        if len(df_cq_periode) > 0:
            taux_rejet = (len(df_cq_periode[df_cq_periode["conforme"] == "NON"]) / len(df_cq_periode)) * 100

    return {"total_ofs": total_ofs, "repartition_statut": repartition, "taux_rejet": taux_rejet}

def get_kpis_crm(date_debut: pd.Timestamp, date_fin: pd.Timestamp) -> dict:
    df_opp = charger_donnees("pipeline")

    if df_opp.empty:
        return {"pipeline_pondere": 0.0, "taux_conversion": 0.0, "performance_commerciaux": pd.DataFrame()}

    for col in ["valeur_estimee", "probabilite_pct"]:
        if col in df_opp.columns:
            df_opp[col] = pd.to_numeric(df_opp[col], errors="coerce").fillna(0)

    col_date = "date_creation" if "date_creation" in df_opp.columns else (df_opp.columns[1] if len(df_opp.columns) > 1 else df_opp.columns[0])
    df_opp["date_obj"] = pd.to_datetime(df_opp[col_date], errors="coerce").dt.tz_localize(None)
    mask_periode = (df_opp["date_obj"] >= date_debut) & (df_opp["date_obj"] <= date_fin)
    df_periode = df_opp[mask_periode].copy()

    if "statut" in df_opp.columns:
        mask_ouvert = df_opp["statut"].isin(["NOUVELLE", "EN_COURS", "QUALIFICATION", "PROPOSITION"])
    else:
        mask_ouvert = pd.Series([False] * len(df_opp))

    df_ouvertes = df_opp[mask_ouvert].copy()
    if not df_ouvertes.empty and "valeur_estimee" in df_ouvertes.columns and "probabilite_pct" in df_ouvertes.columns:
        df_ouvertes["valeur_ponderee"] = df_ouvertes["valeur_estimee"] * (df_ouvertes["probabilite_pct"] / 100)
        pipeline_pondere = df_ouvertes["valeur_ponderee"].sum()
    else:
        pipeline_pondere = 0.0

    taux_conversion = 0.0
    perf = pd.DataFrame()

    if "statut" in df_periode.columns:
        df_cloturees = df_periode[df_periode["statut"].isin(["GAGNEE", "PERDUE"])]
        if len(df_cloturees) > 0:
            nb_gagnees = len(df_cloturees[df_cloturees["statut"] == "GAGNEE"])
            taux_conversion = (nb_gagnees / len(df_cloturees)) * 100

        if "commercial_id" in df_periode.columns:
            df_gagnees = df_periode[df_periode["statut"] == "GAGNEE"]
            if not df_gagnees.empty and "valeur_estimee" in df_gagnees.columns:
                perf = df_gagnees.groupby("commercial_id")["valeur_estimee"].sum().reset_index()
                perf.columns = ["Commercial", "CA Généré"]
                perf = perf.sort_values(by="CA Généré", ascending=False)

    return {"pipeline_pondere": pipeline_pondere, "taux_conversion": taux_conversion, "performance_commerciaux": perf}

def get_kpis_rh(date_debut: pd.Timestamp, date_fin: pd.Timestamp) -> dict:
    df_emp = charger_donnees("employes")
    df_conges = charger_donnees("demandes_conges")

    effectif_actif = 0
    repart_service = pd.DataFrame()

    if not df_emp.empty:
        if "statut" in df_emp.columns:
            df_actifs = df_emp[df_emp["statut"] == "ACTIF"]
        else:
            df_actifs = df_emp

        effectif_actif = len(df_actifs)

        col_service = "departement" if "departement" in df_actifs.columns else ("service" if "service" in df_actifs.columns else None)
        if col_service:
            repart_service = df_actifs[col_service].value_counts().reset_index()
            repart_service.columns = ["Service", "Effectif"]

    conges_attente = 0
    if not df_conges.empty and "statut" in df_conges.columns:
        conges_attente = len(df_conges[df_conges["statut"] == "EN_ATTENTE"])

    return {"effectif_actif": effectif_actif, "repartition_service": repart_service, "conges_attente": conges_attente}

def get_kpis_finance(date_debut: pd.Timestamp, date_fin: pd.Timestamp) -> dict:
    df_cpt = charger_donnees("comptes")
    df_reg = charger_donnees("reglements")

    repartition_comptes = pd.DataFrame()
    if not df_cpt.empty:
        if "solde_initial" in df_cpt.columns:
            df_cpt["solde"] = pd.to_numeric(df_cpt["solde_initial"], errors="coerce").fillna(0)
        else:
            df_cpt["solde"] = 0.0

        if "nom_compte" in df_cpt.columns and "type_compte" in df_cpt.columns:
            repartition_comptes = df_cpt[["nom_compte", "solde", "type_compte"]].copy()

    flux_entrants = 0.0
    flux_sortants = 0.0
    taux_lettrage = 0.0

    if not df_reg.empty:
        if "montant_total" in df_reg.columns:
            df_reg["montant_total"] = pd.to_numeric(df_reg["montant_total"], errors="coerce").fillna(0)
        else:
            df_reg["montant_total"] = 0.0

        if "montant_alloue" in df_reg.columns:
            df_reg["montant_alloue"] = pd.to_numeric(df_reg["montant_alloue"], errors="coerce").fillna(0)
        else:
            df_reg["montant_alloue"] = 0.0

        col_date = "date_reglement" if "date_reglement" in df_reg.columns else (df_reg.columns[1] if len(df_reg.columns) > 1 else df_reg.columns[0])
        df_reg["date_obj"] = pd.to_datetime(df_reg[col_date], errors="coerce").dt.tz_localize(None)

        df_periode = df_reg[(df_reg["date_obj"] >= date_debut) & (df_reg["date_obj"] <= date_fin)].copy()

        if "type_flux" in df_periode.columns:
            flux_entrants = df_periode[df_periode["type_flux"] == "ENCAISSEMENT"]["montant_total"].sum()
            flux_sortants = df_periode[df_periode["type_flux"] == "DECAISSEMENT"]["montant_total"].sum()

            encaiss_periode = df_periode[df_periode["type_flux"] == "ENCAISSEMENT"]
            montant_encaiss = encaiss_periode["montant_total"].sum()
            montant_lettre = encaiss_periode["montant_alloue"].sum()

            if montant_encaiss > 0:
                taux_lettrage = (montant_lettre / montant_encaiss) * 100

    return {
        "repartition_comptes": repartition_comptes,
        "flux_entrants": flux_entrants,
        "flux_sortants": flux_sortants,
        "taux_lettrage": taux_lettrage
    }