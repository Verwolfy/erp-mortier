"""
Logique métier du module Dashboards.
Agrège les données pour les indicateurs clés (KPIs) et graphiques.
Interroge directement Supabase (SQL) via des filtres de dates pour des performances maximales.
"""
import pandas as pd
from datetime import timedelta
from core.strict_reads import (fetch_data_strict as fetch_data,
                               fetch_data_by_date_range_strict as fetch_data_by_date_range)
from core.utils import get_local_now
from core.indicateurs_factures import (validated_documents, in_period, client_invoices,
                                      open_receivables, ageing_balance, numeric_values)
from core.strict_reads import DataReadError
from core.indicateurs_charges import payroll_net_for_period, supplier_operating_payments

def charger_donnees(table_name: str) -> pd.DataFrame:
    """Charge une table entière (réservé aux petites tables type référentiels ou stocks actuels)."""
    return pd.DataFrame(fetch_data(table_name))

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
    treso_dispo = 0.0

    if not df_cpt.empty and "solde_initial" in df_cpt.columns:
        treso_dispo += pd.to_numeric(df_cpt["solde_initial"], errors="coerce").fillna(0).sum()

    if not df_reg.empty and "montant_total" in df_reg.columns and "type_flux" in df_reg.columns:
        df_reg["montant_total"] = pd.to_numeric(df_reg["montant_total"], errors="coerce").fillna(0)
        treso_dispo += df_reg[df_reg["type_flux"] == "ENCAISSEMENT"]["montant_total"].sum()
        treso_dispo -= df_reg[df_reg["type_flux"] == "DECAISSEMENT"]["montant_total"].sum()

    # 3. Alertes Stock (Matières Premières sous seuil)
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

def get_kpis_pnl(date_debut: pd.Timestamp, date_fin: pd.Timestamp) -> dict:
    """Calcule le Compte de Résultat (P&L) de manière optimisée."""
    start_str = date_debut.strftime("%Y-%m-%d")
    end_str = date_fin.strftime("%Y-%m-%d")

    # Fetch uniquement sur la période
    df_fac_periode = pd.DataFrame(fetch_data_by_date_range("factures", "date", start_str, end_str))
    df_reg_periode = pd.DataFrame(fetch_data_by_date_range("reglements", "date_reglement", start_str, end_str))

    df_lignes_fac = charger_donnees("lignes_facture")
    df_pf = charger_donnees("stock_actuel_pf")
    df_frn = charger_donnees("fournisseurs")
    df_paie = charger_donnees("fiches_de_paie") # Filtrage mensuel contrôlé ci-dessous

    # Même périmètre de factures validées pour le CA et les lignes de coût.
    documents = validated_documents(df_fac_periode)
    invoices = client_invoices(documents)
    ca_ht = invoices["montant_ht"].sum()
    cogs = 0.0
    if not invoices.empty:
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
    return {
        "ca_ht": invoices["montant_ht"].sum(), "ca_ttc": ca_ttc,
        "timbre_fiscal": invoices["montant_timbre"].sum(),
        "panier_moyen": ca_ttc / count if count else 0.0,
        "taux_avoirs": credits["montant_ttc"].abs().sum() / ca_ttc * 100 if ca_ttc > 0 else 0.0,
        "nb_factures": count, "balance_agee": balance, "top_clients": top_clients,
    }

def get_kpis_achats(date_debut: pd.Timestamp, date_fin: pd.Timestamp) -> dict:
    start_str = date_debut.strftime("%Y-%m-%d")
    end_str = date_fin.strftime("%Y-%m-%d")

    df_cmd = charger_donnees("commandes_achats") # Besoin global pour commandes en retard
    df_periode = pd.DataFrame(fetch_data_by_date_range("commandes_achats", "date_commande", start_str, end_str))
    df_lignes = charger_donnees("lignes_achats")

    if df_periode.empty:
        return {"montant_total": 0.0, "commandes_retard": 0, "repartition_fournisseurs": pd.DataFrame(), "evolution_prix": pd.DataFrame()}

    col_montant = "montant_total_local" if "montant_total_local" in df_periode.columns else "montant_total"
    if col_montant in df_periode.columns:
        df_periode[col_montant] = pd.to_numeric(df_periode[col_montant], errors="coerce").fillna(0)

    montant_total = df_periode[col_montant].sum()

    # Retards globaux
    now = pd.Timestamp(get_local_now()).tz_localize(None)
    if not df_cmd.empty and "date_voulue" in df_cmd.columns:
        df_cmd["date_voulue_obj"] = pd.to_datetime(df_cmd["date_voulue"], errors="coerce").dt.tz_localize(None)
        mask_retard = (df_cmd["date_voulue_obj"] < now)
        if "statut" in df_cmd.columns:
            mask_retard = mask_retard & (~df_cmd["statut"].isin(["RECEPTIONNE", "TERMINE", "ANNULE"]))
        commandes_retard = len(df_cmd[mask_retard])
    else:
        commandes_retard = 0

    repartition = df_periode.groupby("fournisseur_id")[col_montant].sum().reset_index().sort_values(by=col_montant, ascending=False) if not df_periode.empty and "fournisseur_id" in df_periode.columns else pd.DataFrame()

    evolution_prix = pd.DataFrame()
    if not df_lignes.empty and "commande_achat_id" in df_lignes.columns and "prix_unitaire" in df_lignes.columns:
        df_lignes["prix_unitaire"] = pd.to_numeric(df_lignes["prix_unitaire"], errors="coerce").fillna(0)
        df_periode["date_obj"] = pd.to_datetime(df_periode["date_commande"], errors="coerce").dt.tz_localize(None)
        df_merge = pd.merge(df_lignes, df_periode[["commande_achat_id", "date_obj"]], on="commande_achat_id", how="inner")
        if not df_merge.empty:
            evolution_prix = df_merge[["date_obj", "mp_id", "prix_unitaire"]].dropna()

    return {"montant_total": montant_total, "commandes_retard": commandes_retard, "repartition_fournisseurs": repartition, "evolution_prix": evolution_prix}

def get_kpis_stocks(jours_alerte_peremption: int = 30) -> dict:
    # Le stock actuel n'a pas besoin de filtre temporel
    df_stock_mp = charger_donnees("stock_actuel")
    df_stock_pf = charger_donnees("stock_actuel_pf")
    df_lots = charger_donnees("lots")
    df_ref_mp = charger_donnees("matieres_premieres")

    valeur_mp, valeur_pf, sous_seuil = 0.0, 0.0, 0
    lots_expirants = pd.DataFrame()

    if not df_stock_mp.empty and "quantite_disponible" in df_stock_mp.columns:
        df_stock_mp["qte"] = pd.to_numeric(df_stock_mp["quantite_disponible"], errors="coerce").fillna(0)
        df_stock_mp["cmp"] = pd.to_numeric(df_stock_mp.get("cmp_actuel", 0), errors="coerce").fillna(0)
        valeur_mp = (df_stock_mp["qte"] * df_stock_mp["cmp"]).sum()

        if not df_ref_mp.empty and "mp_id" in df_ref_mp.columns:
            merged = pd.merge(df_stock_mp, df_ref_mp, on="mp_id", how="inner")
            if "stock_mini" in merged.columns:
                merged["mini"] = pd.to_numeric(merged["stock_mini"], errors="coerce").fillna(0)
                sous_seuil = len(merged[merged["qte"] < merged["mini"]])

    if not df_stock_pf.empty and "quantite_disponible" in df_stock_pf.columns:
        df_stock_pf["qte"] = pd.to_numeric(df_stock_pf["quantite_disponible"], errors="coerce").fillna(0)
        df_stock_pf["cout"] = pd.to_numeric(df_stock_pf.get("cout_revient", 0), errors="coerce").fillna(0)
        valeur_pf = (df_stock_pf["qte"] * df_stock_pf["cout"]).sum()

    if not df_lots.empty and "date_peremption" in df_lots.columns:
        now = pd.Timestamp(get_local_now()).tz_localize(None)
        limite = now + timedelta(days=jours_alerte_peremption)
        df_lots["date_peremption_obj"] = pd.to_datetime(df_lots["date_peremption"], errors="coerce").dt.tz_localize(None)

        col_qte = "quantite_restante" if "quantite_restante" in df_lots.columns else "quantite_initiale"
        df_lots["qte_lot"] = pd.to_numeric(df_lots.get(col_qte, 0), errors="coerce").fillna(0)

        mask_lots = (df_lots["qte_lot"] > 0) & (df_lots["date_peremption_obj"] >= now) & (df_lots["date_peremption_obj"] <= limite)

        colonnes_ideales = ["lot_id", "item_id", "date_peremption", col_qte]
        cols_to_select = [col for col in colonnes_ideales if col in df_lots.columns]
        lots_expirants = df_lots[mask_lots][cols_to_select].copy()

    return {
        "valeur_mp": valeur_mp,
        "valeur_pf": valeur_pf,
        "valeur_totale": valeur_mp + valeur_pf,
        "sous_seuil": sous_seuil,
        "lots_expirants": lots_expirants
    }

def get_kpis_production(date_debut: pd.Timestamp, date_fin: pd.Timestamp) -> dict:
    start_str = date_debut.strftime("%Y-%m-%d")
    end_str = date_fin.strftime("%Y-%m-%d")

    df_periode = pd.DataFrame(fetch_data_by_date_range("ordres_fabrication", "date_planification", start_str, end_str))
    df_cq = pd.DataFrame(fetch_data_by_date_range("controle_qualite", "date", start_str, end_str))

    if df_periode.empty:
        return {"total_ofs": 0, "repartition_statut": pd.DataFrame(), "taux_rejet": 0.0}

    total_ofs = len(df_periode)
    repartition = pd.DataFrame()
    if total_ofs > 0 and "statut" in df_periode.columns:
        repartition = df_periode["statut"].value_counts().reset_index()
        repartition.columns = ["Statut", "Volume"]

    taux_rejet = 0.0
    if not df_cq.empty and "conforme" in df_cq.columns:
        rejets = len(df_cq[df_cq["conforme"].astype(str).str.upper().isin(["NON", "FALSE", "REJETE"])])
        taux_rejet = (rejets / len(df_cq)) * 100

    return {"total_ofs": total_ofs, "repartition_statut": repartition, "taux_rejet": taux_rejet}

def get_kpis_crm(date_debut: pd.Timestamp, date_fin: pd.Timestamp) -> dict:
    start_str = date_debut.strftime("%Y-%m-%d")
    end_str = date_fin.strftime("%Y-%m-%d")

    df_opp = charger_donnees("pipeline") # Besoin de toutes pour le pipeline en cours
    df_periode = pd.DataFrame(fetch_data_by_date_range("pipeline", "date_creation", start_str, end_str))

    if df_opp.empty:
        return {"pipeline_pondere": 0.0, "taux_conversion": 0.0, "performance_commerciaux": pd.DataFrame()}

    for col in ["valeur_estimee", "probabilite_pct"]:
        if col in df_opp.columns:
            df_opp[col] = pd.to_numeric(df_opp[col], errors="coerce").fillna(0)
        if not df_periode.empty and col in df_periode.columns:
            df_periode[col] = pd.to_numeric(df_periode[col], errors="coerce").fillna(0)

    # Pipeline en cours sur TOUTE la base
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

    if not df_periode.empty and "statut" in df_periode.columns:
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
    start_str = date_debut.strftime("%Y-%m-%d")
    end_str = date_fin.strftime("%Y-%m-%d")

    df_cpt = charger_donnees("comptes")
    df_periode = pd.DataFrame(fetch_data_by_date_range("reglements", "date_reglement", start_str, end_str))

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

    if not df_periode.empty:
        for col in ["montant_total", "montant_alloue"]:
            if col in df_periode.columns:
                df_periode[col] = pd.to_numeric(df_periode[col], errors="coerce").fillna(0)
            else:
                df_periode[col] = 0.0

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