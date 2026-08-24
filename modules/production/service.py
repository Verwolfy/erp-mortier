"""
Logique métier du module Production.
Gère les Recettes, LignesRecette, les OF (Machine à états & CQ) et la traçabilité des consommations.
Conforme au schéma officiel docs/schema_donnees.md.
"""
import pandas as pd
from core.db_service import fetch_data, insert_hybrid, update_hybrid
from core.utils import generate_unique_id, generate_technical_id, get_local_now
from modules.stocks.service import enregistrer_sortie_mp, enregistrer_entree_pf, get_stock_actuel_mp

def get_recettes() -> pd.DataFrame:
    """Récupère toutes les recettes depuis Supabase."""
    return pd.DataFrame(fetch_data("recettes"))

def get_lignes_recette(recette_id: str = None) -> pd.DataFrame:
    """Récupère les lignes de recette."""
    df = pd.DataFrame(fetch_data("lignes_recette"))
    if recette_id and not df.empty and "recette_id" in df.columns:
        return df[df["recette_id"] == recette_id]
    return df

def get_ordres_fabrication() -> pd.DataFrame:
    """Récupère tous les ordres de fabrication."""
    return pd.DataFrame(fetch_data("ordres_fabrication"))

def get_consommations_of(of_id: str = None) -> pd.DataFrame:
    """Récupère les consommations de matières par OF."""
    df = pd.DataFrame(fetch_data("consommations_of"))
    if of_id and not df.empty and "of_id" in df.columns:
        return df[df["of_id"] == of_id]
    return df

def get_controles_qualite(of_id: str = None) -> pd.DataFrame:
    """Récupère le registre des contrôles qualité."""
    df = pd.DataFrame(fetch_data("controle_qualite"))
    if of_id and not df.empty and "of_id" in df.columns:
        return df[df["of_id"] == of_id]
    return df

def create_recette(pf_id: str, version: str, rendement_unite: float, instructions: str, panier_lignes: list) -> str:
    """Crée une nouvelle nomenclature/recette et ses lignes de composants."""
    df_recettes = get_recettes()
    exist_ids = df_recettes["recette_id"].tolist() if not df_recettes.empty and "recette_id" in df_recettes.columns else []
    recette_id = generate_unique_id("REC", exist_ids)
    date_effet = get_local_now().strftime("%Y-%m-%d")

    data_recette = {
        "recette_id": recette_id, "pf_id": pf_id, "version": version,
        "rendement_unite": rendement_unite, "instructions": instructions,
        "date_effet": date_effet, "actif": "OUI"
    }
    insert_hybrid("recettes", data_recette)

    for item in panier_lignes:
        ligne_id = generate_technical_id("LRC")
        data_ligne = {
            "ligne_recette_id": ligne_id, "recette_id": recette_id,
            "mp_id": item["mp_id"], "quantite_par_unite": item["quantite_par_unite"]
        }
        insert_hybrid("lignes_recette", data_ligne)

    return recette_id

def create_ordre_fabrication(pf_id: str, recette_id: str, sku_id: str, quantite_prevue: float, date_planification: str, notes: str) -> str:
    """Génère un Ordre de Fabrication (OF) avec préfixe OF-XXXX."""
    df_ofs = get_ordres_fabrication()
    exist_ids = df_ofs["of_id"].tolist() if not df_ofs.empty and "of_id" in df_ofs.columns else []
    of_id = generate_unique_id("OF", exist_ids)

    data_of = {
        "of_id": of_id, "pf_id": pf_id, "recette_id": recette_id, "sku_id": sku_id,
        "quantite_prevue": quantite_prevue, "quantite_produite": 0.0,
        "date_planification": date_planification, "date_debut": "", "date_fin": "",
        "statut": "PLANIFIE", "cout_total": 0.0, "notes": notes
    }
    insert_hybrid("ordres_fabrication", data_of)
    return of_id

def changer_statut_of(of_id: str, nouveau_statut: str):
    """Met à jour le statut et horodate l'OF selon sa phase de production."""
    updates = {"statut": nouveau_statut}
    date_jour = get_local_now().strftime("%Y-%m-%d")

    if nouveau_statut == "EN_COURS":
        updates["date_debut"] = date_jour
    elif nouveau_statut in ["TERMINE", "REJETE"]:
        updates["date_fin"] = date_jour

    update_hybrid("ordres_fabrication", "of_id", of_id, updates)

def enregistrer_controle_qualite(
    of_id: str,
    conforme: str,
    remarques: str,
    controleur: str,
    quantite_produite: float = 0.0,
    emballage_mp_id: str = None,
    emballage_consomme: float = 0.0
):
    """
    Enregistre le CQ et clôture l'OF si conforme :
    1. Validation des stocks disponibles.
    2. Enregistrement des consommations détaillées (consommations_of).
    3. Déduction FIFO des matières et entrée en stock du produit fini.
    """
    if conforme == "OUI" and quantite_produite <= 0:
        raise ValueError("Pour déclarer un OF conforme, la quantité produite doit être supérieure à zéro.")

    cq_id = generate_technical_id("QC")
    date_jour = get_local_now().strftime("%Y-%m-%d %H:%M:%S")

    data_cq = {
        "qc_id": cq_id, "of_id": of_id, "date": date_jour,
        "conforme": conforme, "remarques": remarques, "controleur": controleur
    }
    insert_hybrid("controle_qualite", data_cq)

    if conforme == "OUI":
        df_ofs = get_ordres_fabrication()
        of = df_ofs[df_ofs["of_id"] == of_id].iloc[0]

        recette_id = of["recette_id"]
        sku_id = of["sku_id"]

        df_lignes = get_lignes_recette()
        lignes_recette = df_lignes[df_lignes["recette_id"] == recette_id]

        # --- PASSE 1 : SIMULATION DE DISPONIBILITÉ ---
        df_stock_mp = get_stock_actuel_mp()
        besoins_of = []

        for _, ligne in lignes_recette.iterrows():
            qte_necessaire = float(ligne["quantite_par_unite"]) * quantite_produite
            mp_id = ligne["mp_id"]
            besoins_of.append((mp_id, qte_necessaire))

        if emballage_mp_id and str(emballage_mp_id).strip() and emballage_consomme > 0:
            besoins_of.append((emballage_mp_id, emballage_consomme))

        besoins_consolides = {}
        for mp_id, qte in besoins_of:
            besoins_consolides[mp_id] = besoins_consolides.get(mp_id, 0.0) + qte

        for mp_id, qte_necessaire in besoins_consolides.items():
            stock_existant = df_stock_mp[df_stock_mp["mp_id"] == mp_id] if not df_stock_mp.empty and "mp_id" in df_stock_mp.columns else pd.DataFrame()
            if stock_existant.empty:
                raise ValueError(f"Stock physique introuvable pour la matière première {mp_id}.")

            qte_actuelle = float(stock_existant.iloc[0].get("quantite_disponible", 0))
            if qte_actuelle < qte_necessaire:
                raise ValueError(f"Stock insuffisant pour {mp_id}. Requis: {qte_necessaire}, Disponible: {qte_actuelle}")

        # --- PASSE 2 : EXÉCUTION & TRAÇABILITÉ DES CONSUMMATIONS ---
        cout_total_mp = 0.0

        # Sortie Vrac Chimie + Traçabilité dans consommations_of
        for _, ligne in lignes_recette.iterrows():
            mp_id = ligne["mp_id"]
            qte = float(ligne["quantite_par_unite"]) * quantite_produite
            cout = enregistrer_sortie_mp(mp_id, qte, f"Consommation Vrac OF {of_id}")
            cout_total_mp += cout

            # Traçabilité consommations_of
            cnof_id = generate_technical_id("CNOF")
            data_consommation = {
                "consommation_id": cnof_id,
                "of_id": of_id,
                "mp_id": mp_id,
                "lot_id": f"FIFO-{of_id}",
                "quantite_consommee": qte
            }
            insert_hybrid("consommations_of", data_consommation)

        # Sortie Emballage Logistique + Traçabilité
        if emballage_mp_id and str(emballage_mp_id).strip() and emballage_consomme > 0:
            cout_emb = enregistrer_sortie_mp(emballage_mp_id, emballage_consomme, f"Consommation Emballage OF {of_id}")
            cout_total_mp += cout_emb

            cnof_emb_id = generate_technical_id("CNOF")
            data_consommation_emb = {
                "consommation_id": cnof_emb_id,
                "of_id": of_id,
                "mp_id": emballage_mp_id,
                "lot_id": f"EMB-{of_id}",
                "quantite_consommee": emballage_consomme
            }
            insert_hybrid("consommations_of", data_consommation_emb)

        cout_unitaire_pf = cout_total_mp / quantite_produite if quantite_produite > 0 else 0.0

        # Entrée du Produit Fini en Stock
        enregistrer_entree_pf(sku_id, quantite_produite, cout_unitaire_pf, f"Production OF {of_id}", "")

        # Clôture finale de l'OF
        update_hybrid("ordres_fabrication", "of_id", of_id, {
            "statut": "TERMINE",
            "date_fin": get_local_now().strftime("%Y-%m-%d"),
            "quantite_produite": quantite_produite,
            "cout_total": round(cout_total_mp, 2)
        })
    else:
        changer_statut_of(of_id, "REJETE")

def auto_create_of_from_vente(sku_id: str, quantite_manquante: float, facture_id: str) -> str:
    """Génère automatiquement un OF depuis le module Ventes pour combler une rupture de stock."""
    df_skus = pd.DataFrame(fetch_data("sku_conditionnement"))
    if df_skus.empty or "sku_id" not in df_skus.columns:
        raise ValueError("Catalogue des SKU introuvable.")

    sku_row = df_skus[df_skus["sku_id"] == sku_id]
    if sku_row.empty:
        raise ValueError(f"SKU {sku_id} introuvable.")

    pf_id = sku_row.iloc[0]["pf_id"]
    df_recettes = get_recettes()
    if df_recettes.empty:
        raise ValueError("Aucune recette disponible dans le système.")

    recettes_compatibles = df_recettes[(df_recettes["pf_id"] == pf_id) & (df_recettes["actif"] == "OUI")]
    if recettes_compatibles.empty:
        raise ValueError(f"Impossible de lancer la production : Aucune recette active pour le produit {pf_id}.")

    recette_id = recettes_compatibles.iloc[0]["recette_id"]
    notes = f"Urgence : OF automatique pour le document de vente {facture_id}"
    date_planif = get_local_now().strftime("%Y-%m-%d")

    return create_ordre_fabrication(pf_id, recette_id, sku_id, quantite_manquante, date_planif, notes)