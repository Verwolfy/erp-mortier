"""
Logique métier du module Achats.
Respect strict du schéma docs/schema_donnees.md (CommandesAchats, LignesAchats, BonsReception, LignesBonsReception).
Lecture via Supabase, Écriture hybride (Supabase + Google Sheets).
"""
import pandas as pd
from core.db_service import fetch_data, insert_hybrid, update_hybrid
from core.utils import generate_unique_id, generate_technical_id, get_local_now
from modules.stocks.service import enregistrer_entree_mp

def get_commandes() -> pd.DataFrame:
    """Récupère l'historique des commandes d'achats depuis Supabase."""
    return pd.DataFrame(fetch_data("commandes_achats"))

def get_lignes_achats(commande_id: str = None) -> pd.DataFrame:
    """Récupère les lignes d'achats, optionnellement filtrées par commande."""
    df = pd.DataFrame(fetch_data("lignes_achats"))
    if commande_id and not df.empty and "commande_achat_id" in df.columns:
        return df[df["commande_achat_id"] == commande_id]
    return df

def get_bons_reception() -> pd.DataFrame:
    """Récupère la liste des bons de réception."""
    return pd.DataFrame(fetch_data("bons_reception"))

def get_lignes_bons_reception(br_id: str = None) -> pd.DataFrame:
    """Récupère les lignes des bons de réception."""
    df = pd.DataFrame(fetch_data("lignes_bons_reception"))
    if br_id and not df.empty and "bon_reception_id" in df.columns:
        return df[df["bon_reception_id"] == br_id]
    return df

def create_commande_achat(fournisseur_id: str, type_achat: str, devise: str, taux_change: float,
                          mode_paiement: str, delai_paiement: str, date_voulue: str, panier: list) -> str:
    """
    Crée une commande d'achat et ses lignes associées.
    """
    df_cmds = get_commandes()
    exist_ids = df_cmds["commande_achat_id"].tolist() if not df_cmds.empty else []

    cmd_id = generate_unique_id("CMA", exist_ids)
    date_cmd = get_local_now().strftime("%Y-%m-%d")

    montant_total_devise = sum(item["total_devise"] for item in panier)
    montant_total_local = montant_total_devise * float(taux_change)

    data_cmd = {
        "commande_achat_id": cmd_id, "date_commande": date_cmd, "fournisseur_id": fournisseur_id,
        "type_achat": type_achat, "devise": devise, "taux_change": taux_change,
        "montant_total_devise": montant_total_devise, "montant_total_local": montant_total_local,
        "mode_paiement": mode_paiement, "delai_paiement": delai_paiement,
        "date_voulue": str(date_voulue), "statut": "EN_ATTENTE"
    }

    insert_hybrid("commandes_achats", data_cmd)

    for item in panier:
        ligne_id = generate_technical_id("LAC")
        data_ligne = {
            "ligne_achat_id": ligne_id, "commande_achat_id": cmd_id, "mp_id": item["mp_id"],
            "unite_cond": item["unite_cond"], "qte_cond": item["qte_cond"],
            "qte_totale": item["qte_totale"], "prix_unitaire": item["prix_unitaire"],
            "total_devise": item["total_devise"]
        }
        insert_hybrid("lignes_achats", data_ligne)

    return cmd_id

def creer_bon_reception(commande_achat_id: str, date_reception: str, controle_conformite: str,
                        remarques: str, items_recus: list, date_peremption: str = "") -> str:
    """
    Génère un Bon de Réception (BR), enregistre les lignes de réception et
    alimente automatiquement le stock de matières premières/emballages (FIFO/CMP).
    """
    df_br = get_bons_reception()
    exist_ids = df_br["bon_reception_id"].tolist() if not df_br.empty and "bon_reception_id" in df_br.columns else []
    br_id = generate_unique_id("BR", exist_ids)

    data_br = {
        "bon_reception_id": br_id,
        "commande_achat_id": commande_achat_id,
        "date_reception": date_reception,
        "controle_conformite": controle_conformite,
        "remarques": remarques
    }
    insert_hybrid("bons_reception", data_br)

    for item in items_recus:
        mp_id = item["mp_id"]
        qte_recue = float(item["quantite_recue"])
        prix_u = float(item.get("prix_unitaire", 0.0))

        if qte_recue > 0:
            # 1. Alimentation automatique du stock physique et création du lot via le service Stocks
            enregistrer_entree_mp(
                mp_id=mp_id,
                quantite=qte_recue,
                prix_entree=prix_u,
                reference=f"BR {br_id} (Cmd {commande_achat_id})",
                date_peremption=date_peremption
            )

            # 2. Enregistrement de la ligne de Bon de Réception
            ligne_br_id = generate_technical_id("LBR")
            data_ligne_br = {
                "ligne_br_id": ligne_br_id,
                "bon_reception_id": br_id,
                "mp_id": mp_id,
                "quantite_recue": qte_recue,
                "lot_attribue_id": f"BR-{br_id}"
            }
            insert_hybrid("lignes_bons_reception", data_ligne_br)

    # 3. Clôture de la commande d'achat
    update_hybrid("commandes_achats", "commande_achat_id", commande_achat_id, {"statut": "RECEPTIONNE"})

    return br_id