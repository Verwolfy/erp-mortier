"""
Logique métier du module Stocks.
Gère les mouvements, les lots, et la mise à jour des stocks.
Lecture via Supabase, Écriture hybride (Supabase + Google Sheets).
Conforme au schéma docs/schema_reference.md.
"""
import pandas as pd
from core.db_service import fetch_data, insert_hybrid, update_hybrid
from core.utils import generate_technical_id, get_local_now

def get_stock_actuel_mp() -> pd.DataFrame:
    return pd.DataFrame(fetch_data("stock_actuel"))

def get_stock_actuel_pf() -> pd.DataFrame:
    return pd.DataFrame(fetch_data("stock_actuel_pf"))

def get_mouvements() -> pd.DataFrame:
    return pd.DataFrame(fetch_data("mouvements"))

def get_mouvements_pf() -> pd.DataFrame:
    return pd.DataFrame(fetch_data("mouvements_pf"))

def get_lots() -> pd.DataFrame:
    return pd.DataFrame(fetch_data("lots"))

def enregistrer_entree_mp(mp_id: str, quantite: float, prix_entree: float, reference: str, date_peremption: str):
    """Enregistre une entrée en stock MP."""
    date_jour = get_local_now().strftime("%Y-%m-%d %H:%M:%S")
    lot_id = generate_technical_id("LOT")
    mvt_id = generate_technical_id("MOUV")

    data_lot = {
        "lot_id": lot_id, "item_id": mp_id, "type_item": "MP",
        "date_creation": date_jour, "date_peremption": date_peremption,
        "quantite_initiale": quantite, "quantite_restante": quantite, "statut": "ACTIF"
    }

    data_mouv = {
        "mouvement_id": mvt_id, "date": date_jour, "type_mouvement": "ENTREE",
        "mp_id": mp_id, "quantite": quantite, "reference": reference,
        "lot_id": lot_id, "prix_entree": prix_entree
    }

    df_stock = get_stock_actuel_mp()
    stock_existant = df_stock[df_stock["mp_id"] == mp_id] if not df_stock.empty and "mp_id" in df_stock.columns else pd.DataFrame()

    if not stock_existant.empty:
        qte_actuelle = float(stock_existant.iloc[0].get("quantite_disponible", 0))
        cmp_actuel = float(stock_existant.iloc[0].get("cmp_actuel", 0))

        valeur_totale_actuelle = qte_actuelle * cmp_actuel
        valeur_nouvelle_entree = quantite * prix_entree
        nouvelle_qte_totale = qte_actuelle + quantite
        nouveau_cmp = (valeur_totale_actuelle + valeur_nouvelle_entree) / nouvelle_qte_totale if nouvelle_qte_totale > 0 else 0

        update_hybrid("stock_actuel", "mp_id", mp_id, {
            "quantite_disponible": nouvelle_qte_totale,
            "cmp_actuel": round(nouveau_cmp, 2),
            "derniere_maj": date_jour
        })
    else:
        data_stock = {
            "mp_id": mp_id, "quantite_disponible": quantite,
            "cmp_actuel": round(prix_entree, 2), "derniere_maj": date_jour
        }
        insert_hybrid("stock_actuel", data_stock)

    insert_hybrid("lots", data_lot)
    insert_hybrid("mouvements", data_mouv)

def enregistrer_sortie_mp(mp_id: str, quantite: float, reference: str) -> float:
    """Décrémente le stock MP et applique la règle FIFO sur les lots."""
    date_jour = get_local_now().strftime("%Y-%m-%d %H:%M:%S")
    df_stock = get_stock_actuel_mp()

    if df_stock.empty or "mp_id" not in df_stock.columns:
        raise ValueError(f"Base de stock vide ou non configurée.")

    stock_existant = df_stock[df_stock["mp_id"] == mp_id]

    if stock_existant.empty:
        raise ValueError(f"Stock introuvable pour la matière {mp_id}")

    qte_actuelle = float(stock_existant.iloc[0].get("quantite_disponible", 0))
    cmp_actuel = float(stock_existant.iloc[0].get("cmp_actuel", 0))

    if qte_actuelle < quantite:
        raise ValueError(f"Stock global insuffisant pour {mp_id}. Requis: {quantite}, Disponible: {qte_actuelle}")

    # 1. Règle FIFO sur les Lots
    df_lots = get_lots()
    if df_lots.empty or "item_id" not in df_lots.columns:
        raise ValueError("La table des lots est vide ou mal configurée.")

    lots_actifs = df_lots[(df_lots["item_id"] == mp_id) & (df_lots["statut"] == "ACTIF")].sort_values(by="date_creation")

    qte_a_deduire = quantite
    cout_total = 0.0
    lots_to_update = []
    mouvements_to_insert = []

    for _, lot in lots_actifs.iterrows():
        if qte_a_deduire <= 0: break

        restant = float(lot.get("quantite_restante", 0))
        if restant <= 0: continue

        lot_id = lot["lot_id"]
        qte_prelevee = min(restant, qte_a_deduire)
        nouveau_restant = restant - qte_prelevee

        cout_total += (qte_prelevee * cmp_actuel)

        lots_to_update.append({
            "lot_id": lot_id,
            "quantite_restante": nouveau_restant,
            "statut": "EPUISE" if nouveau_restant == 0 else "ACTIF"
        })

        mvt_id = generate_technical_id("MOUV")
        mouvements_to_insert.append({
            "mouvement_id": mvt_id, "date": date_jour, "type_mouvement": "SORTIE",
            "mp_id": mp_id, "quantite": qte_prelevee, "reference": reference,
            "lot_id": lot_id, "prix_entree": cmp_actuel
        })

        qte_a_deduire -= qte_prelevee

    if qte_a_deduire > 0:
        raise ValueError(f"Incohérence des lots : stock physique insuffisant pour {mp_id}. Manque {qte_a_deduire}.")

    # 2. Exécution des écritures
    update_hybrid("stock_actuel", "mp_id", mp_id, {
        "quantite_disponible": qte_actuelle - quantite,
        "derniere_maj": date_jour
    })

    for ltu in lots_to_update:
        update_hybrid("lots", "lot_id", ltu["lot_id"], {
            "quantite_restante": ltu["quantite_restante"],
            "statut": ltu["statut"]
        })

    for mvt in mouvements_to_insert:
        insert_hybrid("mouvements", mvt)

    return cout_total

def enregistrer_entree_pf(sku_id: str, quantite: float, cout_unitaire: float, reference: str, date_peremption: str):
    """Enregistre l'entrée en stock d'un produit fini (suite à production)."""
    date_jour = get_local_now().strftime("%Y-%m-%d %H:%M:%S")
    lot_id = generate_technical_id("LOT")
    mvt_id = generate_technical_id("MOUVPF")

    data_lot = {
        "lot_id": lot_id, "item_id": sku_id, "type_item": "PF",
        "date_creation": date_jour, "date_peremption": date_peremption,
        "quantite_initiale": quantite, "quantite_restante": quantite, "statut": "ACTIF"
    }

    data_mouv = {
        "mouvement_pf_id": mvt_id, "date": date_jour, "type_mouvement": "ENTREE",
        "sku_id": sku_id, "quantite": quantite, "reference": reference,
        "lot_id": lot_id, "cout_unitaire": cout_unitaire
    }

    df_stock = get_stock_actuel_pf()
    stock_existant = df_stock[df_stock["sku_id"] == sku_id] if not df_stock.empty and "sku_id" in df_stock.columns else pd.DataFrame()

    if not stock_existant.empty:
        qte_actuelle = float(stock_existant.iloc[0].get("quantite_disponible", 0))
        cout_actuel = float(stock_existant.iloc[0].get("cout_revient", 0))

        valeur_totale_actuelle = qte_actuelle * cout_actuel
        valeur_nouvelle_entree = quantite * cout_unitaire
        nouvelle_qte_totale = qte_actuelle + quantite
        nouveau_cout = (valeur_totale_actuelle + valeur_nouvelle_entree) / nouvelle_qte_totale if nouvelle_qte_totale > 0 else 0

        update_hybrid("stock_actuel_pf", "sku_id", sku_id, {
            "quantite_disponible": nouvelle_qte_totale,
            "cout_revient": round(nouveau_cout, 2),
            "derniere_maj": date_jour
        })
    else:
        data_stock = {
            "sku_id": sku_id, "quantite_disponible": quantite,
            "cout_revient": round(cout_unitaire, 2), "derniere_maj": date_jour
        }
        insert_hybrid("stock_actuel_pf", data_stock)

    insert_hybrid("lots", data_lot)
    insert_hybrid("mouvements_pf", data_mouv)

def enregistrer_sortie_pf(sku_id: str, quantite: float, reference: str):
    """Décrémente le stock de produit fini, applique le FIFO et trace les lots."""
    date_jour = get_local_now().strftime("%Y-%m-%d %H:%M:%S")
    df_stock = get_stock_actuel_pf()

    if df_stock.empty or "sku_id" not in df_stock.columns:
        raise ValueError(f"Base de stock PF vide ou non configurée.")

    stock_existant = df_stock[df_stock["sku_id"] == sku_id]

    if stock_existant.empty:
        raise ValueError(f"Stock introuvable pour le produit {sku_id}")

    qte_actuelle = float(stock_existant.iloc[0].get("quantite_disponible", 0))
    cout_actuel = float(stock_existant.iloc[0].get("cout_revient", 0))

    if qte_actuelle < quantite:
        raise ValueError(f"Stock global insuffisant pour {sku_id}. Requis: {quantite}, Disponible: {qte_actuelle}")

    # 1. Règle FIFO sur les Lots
    df_lots = get_lots()
    if df_lots.empty or "item_id" not in df_lots.columns:
        raise ValueError("La table des lots est vide ou mal configurée.")

    lots_actifs = df_lots[(df_lots["item_id"] == sku_id) & (df_lots["statut"] == "ACTIF")].sort_values(by="date_creation")

    qte_a_deduire = quantite
    lots_to_update = []
    mouvements_to_insert = []

    for _, lot in lots_actifs.iterrows():
        if qte_a_deduire <= 0: break

        restant = float(lot.get("quantite_restante", 0))
        if restant <= 0: continue

        lot_id = lot["lot_id"]
        qte_prelevee = min(restant, qte_a_deduire)
        nouveau_restant = restant - qte_prelevee

        lots_to_update.append({
            "lot_id": lot_id,
            "quantite_restante": nouveau_restant,
            "statut": "EPUISE" if nouveau_restant == 0 else "ACTIF"
        })

        mvt_id = generate_technical_id("MOUVPF")
        mouvements_to_insert.append({
            "mouvement_pf_id": mvt_id, "date": date_jour, "type_mouvement": "SORTIE",
            "sku_id": sku_id, "quantite": qte_prelevee, "reference": reference,
            "lot_id": lot_id, "cout_unitaire": cout_actuel
        })

        qte_a_deduire -= qte_prelevee

    if qte_a_deduire > 0:
        raise ValueError(f"Incohérence des lots : stock physique insuffisant pour {sku_id}. Manque {qte_a_deduire}.")

    # 2. Exécution des écritures
    update_hybrid("stock_actuel_pf", "sku_id", sku_id, {
        "quantite_disponible": qte_actuelle - quantite,
        "derniere_maj": date_jour
    })

    for ltu in lots_to_update:
        update_hybrid("lots", "lot_id", ltu["lot_id"], {
            "quantite_restante": ltu["quantite_restante"],
            "statut": ltu["statut"]
        })

    for mvt in mouvements_to_insert:
        insert_hybrid("mouvements_pf", mvt)