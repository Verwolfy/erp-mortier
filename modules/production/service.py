"""
Logique métier du module Production.
Gère les Recettes, LignesRecette, et les OF (Machine à états & CQ).
Intègre la décrémentation des emballages logistiques liés au SKU.
Lecture via Supabase, Écriture hybride (Supabase + Google Sheets).
Conforme au schéma docs/schema_reference.md.
"""
import pandas as pd
from core.db_service import fetch_data, insert_hybrid, update_hybrid
from core.utils import generate_unique_id, generate_technical_id, get_local_now
from modules.stocks.service import enregistrer_sortie_mp, enregistrer_entree_pf, get_stock_actuel_mp

def get_recettes() -> pd.DataFrame:
    return pd.DataFrame(fetch_data("recettes"))

def get_lignes_recette() -> pd.DataFrame:
    return pd.DataFrame(fetch_data("lignes_recette"))

def get_ordres_fabrication() -> pd.DataFrame:
    return pd.DataFrame(fetch_data("ordres_fabrication"))

def create_recette(pf_id: str, version: str, rendement_unite: float, instructions: str, panier_lignes: list) -> str:
    df_recettes = get_recettes()
    exist_ids = df_recettes["recette_id"].tolist() if not df_recettes.empty else []
    recette_id = generate_unique_id("REC", exist_ids)
    date_effet = get_local_now().strftime("%Y-%m-%d")

    data_recette = {
        "recette_id": recette_id, "pf_id": pf_id, "version": version,
        "rendement_unite": rendement_unite, "instructions": instructions,
        "date_effet": date_effet, "actif": "OUI"
    }
    cols_recette = ["recette_id", "pf_id", "version", "rendement_unite", "instructions", "date_effet", "actif"]

    insert_hybrid("recettes", "production", "Recettes", data_recette, cols_recette)

    cols_lignes = ["ligne_recette_id", "recette_id", "mp_id", "quantite_par_unite"]
    for item in panier_lignes:
        ligne_id = generate_technical_id("LRC")
        data_ligne = {
            "ligne_recette_id": ligne_id, "recette_id": recette_id,
            "mp_id": item["mp_id"], "quantite_par_unite": item["quantite_par_unite"]
        }
        insert_hybrid("lignes_recette", "production", "LignesRecette", data_ligne, cols_lignes)

    return recette_id

def create_ordre_fabrication(pf_id: str, recette_id: str, sku_id: str, quantite_prevue: float, date_planification: str, notes: str) -> str:
    df_ofs = get_ordres_fabrication()
    exist_ids = df_ofs["of_id"].tolist() if not df_ofs.empty else []
    of_id = generate_unique_id("OF", exist_ids)

    data_of = {
        "of_id": of_id, "pf_id": pf_id, "recette_id": recette_id, "sku_id": sku_id,
        "quantite_prevue": quantite_prevue, "quantite_produite": 0.0,
        "date_planification": date_planification, "date_debut": "", "date_fin": "",
        "statut": "PLANIFIE", "cout_total": 0.0, "notes": notes
    }
    cols_of = ["of_id", "pf_id", "recette_id", "sku_id", "quantite_prevue", "quantite_produite", "date_planification", "date_debut", "date_fin", "statut", "cout_total", "notes"]

    insert_hybrid("ordres_fabrication", "production", "OrdresFabrication", data_of, cols_of)
    return of_id

def changer_statut_of(of_id: str, nouveau_statut: str):
    """Met à jour le statut et horodate l'OF selon sa phase."""
    updates = {"statut": nouveau_statut}
    date_jour = get_local_now().strftime("%Y-%m-%d")

    if nouveau_statut == "EN_COURS":
        updates["date_debut"] = date_jour
    elif nouveau_statut in ["TERMINE", "REJETE"]:
        updates["date_fin"] = date_jour

    update_hybrid("ordres_fabrication", "production", "OrdresFabrication", "of_id", of_id, updates)

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
    Inscrit le CQ. S'il est conforme, exécute la clôture de façon atomique (en 2 passes) :
    1. Simulation pour s'assurer que tout le stock MP (vrac + emballages) est suffisant.
    2. Sortie réelle FIFO des MP -> Entrée du PF avec calcul de coût.
    """
    if conforme == "OUI" and quantite_produite <= 0:
        raise ValueError("Pour déclarer un OF conforme, la quantité produite doit être supérieure à zéro.")

    cq_id = generate_technical_id("QC")
    date_jour = get_local_now().strftime("%Y-%m-%d %H:%M:%S")

    data_cq = {
        "qc_id": cq_id, "of_id": of_id, "date": date_jour,
        "conforme": conforme, "remarques": remarques, "controleur": controleur
    }
    cols_cq = ["qc_id", "of_id", "date", "conforme", "remarques", "controleur"]
    insert_hybrid("controle_qualite", "production", "ControleQualite", data_cq, cols_cq)

    if conforme == "OUI":
        df_ofs = get_ordres_fabrication()
        of = df_ofs[df_ofs["of_id"] == of_id].iloc[0]

        recette_id = of["recette_id"]
        sku_id = of["sku_id"]

        df_lignes = get_lignes_recette()
        lignes_recette = df_lignes[df_lignes["recette_id"] == recette_id]

        # --- PASSE 1 : VÉRIFICATION (Simulation Vrac + Emballage) ---
        df_stock_mp = get_stock_actuel_mp()
        besoins_of = []

        # 1A. Besoins Vrac (Chimique)
        for _, ligne in lignes_recette.iterrows():
            qte_necessaire = float(ligne["quantite_par_unite"]) * quantite_produite
            mp_id = ligne["mp_id"]
            besoins_of.append((mp_id, qte_necessaire))

        # 1B. Besoins Emballage (Logistique)
        if emballage_mp_id and emballage_mp_id.strip() and emballage_consomme > 0:
            besoins_of.append((emballage_mp_id, emballage_consomme))

        # 1C. Contrôle de disponibilité globale
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

        # --- PASSE 2 : EXÉCUTION RÉELLE ---
        cout_total_mp = 0.0

        # Sortie Vrac
        for _, ligne in lignes_recette.iterrows():
            qte = float(ligne["quantite_par_unite"]) * quantite_produite
            cout = enregistrer_sortie_mp(ligne["mp_id"], qte, f"Consommation Vrac OF {of_id}")
            cout_total_mp += cout

        # Sortie Emballage
        if emballage_mp_id and emballage_mp_id.strip() and emballage_consomme > 0:
            cout_emb = enregistrer_sortie_mp(emballage_mp_id, emballage_consomme, f"Consommation Emballage OF {of_id}")
            cout_total_mp += cout_emb

        cout_unitaire_pf = cout_total_mp / quantite_produite if quantite_produite > 0 else 0.0

        # Entrée en stock du Produit Fini
        date_peremption = ""
        enregistrer_entree_pf(sku_id, quantite_produite, cout_unitaire_pf, f"Production OF {of_id}", date_peremption)

        # Clôture de l'OF
        update_hybrid("ordres_fabrication", "production", "OrdresFabrication", "of_id", of_id, {
            "statut": "TERMINE",
            "date_fin": get_local_now().strftime("%Y-%m-%d"),
            "quantite_produite": quantite_produite,
            "cout_total": round(cout_total_mp, 2)
        })
    else:
        changer_statut_of(of_id, "REJETE")