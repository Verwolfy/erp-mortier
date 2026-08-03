"""
Logique métier du module Achats.
Respect strict du schéma docs/schema_reference.md (CommandesAchats, LignesAchats).
Lecture via Supabase, Écriture hybride (Supabase + Google Sheets).
"""
import pandas as pd
from core.db_service import fetch_data, insert_hybrid
from core.utils import generate_unique_id, generate_technical_id, get_local_now

def get_commandes() -> pd.DataFrame:
    """Récupère l'historique des commandes d'achats depuis Supabase."""
    return pd.DataFrame(fetch_data("commandes_achats"))

def create_commande_achat(fournisseur_id: str, type_achat: str, devise: str, taux_change: float,
                          mode_paiement: str, delai_paiement: str, date_voulue: str, panier: list) -> str:
    """
    Crée une commande d'achat et ses lignes associées.
    """
    df_cmds = get_commandes()
    exist_ids = df_cmds["commande_achat_id"].tolist() if not df_cmds.empty else []

    # ID Séquentiel pour la commande (ex: CMA-0001)
    cmd_id = generate_unique_id("CMA", exist_ids)
    date_cmd = get_local_now().strftime("%Y-%m-%d")

    # Calcul des totaux
    montant_total_devise = sum(item["total_devise"] for item in panier)
    montant_total_local = montant_total_devise * float(taux_change)

    # Préparation de l'en-tête
    data_cmd = {
        "commande_achat_id": cmd_id, "date_commande": date_cmd, "fournisseur_id": fournisseur_id,
        "type_achat": type_achat, "devise": devise, "taux_change": taux_change,
        "montant_total_devise": montant_total_devise, "montant_total_local": montant_total_local,
        "mode_paiement": mode_paiement, "delai_paiement": delai_paiement,
        "date_voulue": str(date_voulue), "statut": "EN_ATTENTE"
    }

    # Insertion groupée via API Hybride (Supabase d'abord, puis Sheets avec déduction automatique)
    insert_hybrid("commandes_achats", data_cmd)

    # Préparation et insertion des lignes d'achats
    for item in panier:
        # ID Technique (UUID) préfixé LAC
        ligne_id = generate_technical_id("LAC")

        data_ligne = {
            "ligne_achat_id": ligne_id, "commande_achat_id": cmd_id, "mp_id": item["mp_id"],
            "unite_cond": item["unite_cond"], "qte_cond": item["qte_cond"],
            "qte_totale": item["qte_totale"], "prix_unitaire": item["prix_unitaire"],
            "total_devise": item["total_devise"]
        }
        insert_hybrid("lignes_achats", data_ligne)

    return cmd_id