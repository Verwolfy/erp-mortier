"""
Script d'automatisation : Audit et recalcul des stocks (Matières Premières et Produits Finis).
À exécuter quotidiennement via GitHub Actions (idéalement la nuit).
Compare la somme des mouvements avec le solde actuel et corrige les écarts.
"""
import os
import pandas as pd
from datetime import datetime
from supabase import create_client

# Configuration Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


def auditer_et_corriger_stock_mp(supabase):
    """Vérifie le stock des Matières Premières."""
    print("--- 📦 AUDIT DES MATIÈRES PREMIÈRES (MP) ---")

    # 1. Récupérer les données
    mouvements_res = supabase.table("mouvements").select("*").execute()
    stock_res = supabase.table("stock_actuel").select("*").execute()

    df_mouv = pd.DataFrame(mouvements_res.data)
    df_stock = pd.DataFrame(stock_res.data)

    if df_mouv.empty:
        print("Aucun mouvement MP trouvé.")
        return

    # 2. Convertir les quantités selon le type de mouvement (Entrée = +, Sortie = -)
    df_mouv["quantite"] = pd.to_numeric(df_mouv["quantite"], errors="coerce").fillna(0)
    df_mouv["qte_reelle"] = df_mouv.apply(
        lambda row: row["quantite"] if str(row["type_mouvement"]).upper() == "ENTREE" else -row["quantite"],
        axis=1
    )

    # 3. Agréger par MP
    stock_calcule = df_mouv.groupby("mp_id")["qte_reelle"].sum().reset_index()

    # 4. Comparer et Corriger
    for _, row_calc in stock_calcule.iterrows():
        mp_id = row_calc["mp_id"]
        qte_theorique = round(row_calc["qte_reelle"], 2)

        # Trouver la ligne correspondante dans le stock actuel
        stock_actuel_row = df_stock[
            df_stock["mp_id"] == mp_id] if not df_stock.empty and "mp_id" in df_stock.columns else pd.DataFrame()
        qte_affichee = round(float(stock_actuel_row.iloc[0]["quantite_disponible"]),
                             2) if not stock_actuel_row.empty else 0.0

        if qte_theorique != qte_affichee:
            print(f"⚠️ Écart détecté sur {mp_id} : Calculé = {qte_theorique} | Affiché = {qte_affichee}")

            # Correction dans Supabase
            if stock_actuel_row.empty:
                supabase.table("stock_actuel").insert({
                    "mp_id": mp_id, "quantite_disponible": qte_theorique, "derniere_maj": datetime.now().isoformat()
                }).execute()
            else:
                supabase.table("stock_actuel").update({
                    "quantite_disponible": qte_theorique, "derniere_maj": datetime.now().isoformat()
                }).eq("mp_id", mp_id).execute()

            print(f"✅ Stock corrigé pour {mp_id}.")


def auditer_et_corriger_stock_pf(supabase):
    """Vérifie le stock des Produits Finis (SKU)."""
    print("--- 🏭 AUDIT DES PRODUITS FINIS (PF) ---")

    mouvements_pf_res = supabase.table("mouvements_pf").select("*").execute()
    stock_pf_res = supabase.table("stock_actuel_pf").select("*").execute()

    df_mouv_pf = pd.DataFrame(mouvements_pf_res.data)
    df_stock_pf = pd.DataFrame(stock_pf_res.data)

    if df_mouv_pf.empty:
        print("Aucun mouvement PF trouvé.")
        return

    df_mouv_pf["quantite"] = pd.to_numeric(df_mouv_pf["quantite"], errors="coerce").fillna(0)
    df_mouv_pf["qte_reelle"] = df_mouv_pf.apply(
        lambda row: row["quantite"] if str(row["type_mouvement"]).upper() == "ENTREE" else -row["quantite"],
        axis=1
    )

    stock_calcule_pf = df_mouv_pf.groupby("sku_id")["qte_reelle"].sum().reset_index()

    for _, row_calc in stock_calcule_pf.iterrows():
        sku_id = row_calc["sku_id"]
        qte_theorique = round(row_calc["qte_reelle"], 2)

        stock_actuel_row = df_stock_pf[df_stock_pf[
                                           "sku_id"] == sku_id] if not df_stock_pf.empty and "sku_id" in df_stock_pf.columns else pd.DataFrame()
        qte_affichee = round(float(stock_actuel_row.iloc[0]["quantite_disponible"]),
                             2) if not stock_actuel_row.empty else 0.0

        if qte_theorique != qte_affichee:
            print(f"⚠️ Écart détecté sur {sku_id} : Calculé = {qte_theorique} | Affiché = {qte_affichee}")

            if stock_actuel_row.empty:
                supabase.table("stock_actuel_pf").insert({
                    "sku_id": sku_id, "quantite_disponible": qte_theorique, "derniere_maj": datetime.now().isoformat()
                }).execute()
            else:
                supabase.table("stock_actuel_pf").update({
                    "quantite_disponible": qte_theorique, "derniere_maj": datetime.now().isoformat()
                }).eq("sku_id", sku_id).execute()

            print(f"✅ Stock corrigé pour {sku_id}.")


def main():
    print(f"=== DÉMARRAGE DE L'AUDIT NOCTURNE DES STOCKS ({datetime.now().strftime('%Y-%m-%d %H:%M')}) ===")
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ Erreur : Variables d'environnement manquantes (SUPABASE_URL, SUPABASE_KEY).")
        return

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    try:
        auditer_et_corriger_stock_mp(supabase)
        auditer_et_corriger_stock_pf(supabase)
        print("=== AUDIT TERMINÉ AVEC SUCCÈS ===")
    except Exception as e:
        print(f"❌ Erreur critique lors de l'audit : {e}")


if __name__ == "__main__":
    main()