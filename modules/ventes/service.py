"""
Logique métier du module Ventes.
Cycle de vie : BROUILLON -> VALIDE -> ANNULE.
Gère les Factures, Avoirs, LignesFacture, Règlements, Bons de Livraison (BL) et Lignes de Livraison.
Lecture Supabase, Écriture hybride (Supabase + Google Sheets).
"""
import pandas as pd
from core.db_service import fetch_data, insert_hybrid, update_hybrid, get_supabase_client
from core.utils import generate_unique_id, generate_technical_id, get_local_now
from modules.stocks.service import enregistrer_sortie_pf, enregistrer_entree_pf

try:
    from num2words import num2words
except ImportError:
    num2words = None


def get_factures() -> pd.DataFrame:
    """Récupère l'historique des factures depuis Supabase."""
    return pd.DataFrame(fetch_data("factures"))


def get_lignes_facture(facture_id: str) -> list:
    """Récupère les lignes d'une facture spécifique."""
    df_lignes = pd.DataFrame(fetch_data("lignes_facture"))
    if not df_lignes.empty and "facture_id" in df_lignes.columns:
        return df_lignes[df_lignes["facture_id"] == facture_id].to_dict('records')
    return []


def get_bons_livraison() -> pd.DataFrame:
    """Récupère la liste des bons de livraison."""
    return pd.DataFrame(fetch_data("bons_livraison"))


def get_lignes_bons_livraison(bl_id: str = None) -> pd.DataFrame:
    """Récupère les lignes des bons de livraison, optionnellement filtrées par BL."""
    df = pd.DataFrame(fetch_data("lignes_bons_livraison"))
    if bl_id and not df.empty and "bl_id" in df.columns:
        return df[df["bl_id"] == bl_id]
    return df


def generer_numero_facture_legal(type_document: str) -> str:
    """Génère un numéro séquentiel strict pour FactureClient ou FactureAvoir via Supabase RPC."""
    df_compteurs = pd.DataFrame(fetch_data("compteurs"))
    if df_compteurs.empty or type_document not in df_compteurs["type_document"].values:
        raise ValueError(f"Le compteur {type_document} n'est pas initialisé dans la base de données.")

    row = df_compteurs[df_compteurs["type_document"] == type_document].iloc[0]
    prefixe = str(row.get("prefixe", "FAC"))
    annee = str(row.get("annee", get_local_now().year))

    try:
        supabase = get_supabase_client()
        response = supabase.rpc("increment_compteur", {"p_type_document": type_document}).execute()
        nouveau_numero = response.data

        update_hybrid("compteurs", "type_document", type_document, {"dernier_numero": nouveau_numero})
        return f"{prefixe}-{annee}-{str(nouveau_numero).zfill(6)}"

    except Exception as e:
        raise Exception(f"Erreur critique lors de la génération du numéro légal : {e}")


def calculer_montants_facture(panier: list, remise_globale: float = 0.0, paiement_especes: bool = False) -> dict:
    """Intègre les remises par ligne, la remise globale, et le calcul du timbre fiscal."""
    montant_ht_brut = 0.0
    total_remises_lignes = 0.0

    for item in panier:
        qte = float(item.get("quantite", 0))
        pu = float(item.get("prix_unitaire", 0))
        remise_ligne = float(item.get("remise", 0))

        ligne_brut = qte * pu
        montant_ht_brut += ligne_brut
        total_remises_lignes += remise_ligne

    total_remise = total_remises_lignes + remise_globale
    net_a_payer_ht = max(0.0, montant_ht_brut - total_remise)

    taux_tva = 0.19
    montant_tva = net_a_payer_ht * taux_tva
    montant_ttc_avant_timbre = net_a_payer_ht + montant_tva

    timbre_fiscal = 0.0
    if paiement_especes:
        timbre_fiscal = min(montant_ttc_avant_timbre * 0.01, 2500.0)

    montant_ttc_final = montant_ttc_avant_timbre + timbre_fiscal

    lettres = ""
    if num2words:
        partie_entiere = int(montant_ttc_final)
        partie_decimale = int(round((montant_ttc_final - partie_entiere) * 100))
        lettres = num2words(partie_entiere, lang='fr') + " Dinars Algériens"
        if partie_decimale > 0:
            lettres += f" et {num2words(partie_decimale, lang='fr')} Centimes"
    else:
        lettres = f"{montant_ttc_final:,.2f} Dinars Algériens"

    return {
        "total_ht": round(montant_ht_brut, 2),
        "total_remise": round(total_remise, 2),
        "net_a_payer": round(net_a_payer_ht, 2),
        "total_tva": round(montant_tva, 2),
        "timbre_fiscal": round(timbre_fiscal, 2),
        "total_ttc": round(montant_ttc_final, 2),
        "montant_lettres": lettres.capitalize()
    }


def create_facture_brouillon(client_id: str, date_echeance: str, panier: list, remise_globale: float = 0.0, paiement_especes: bool = False, is_avoir: bool = False, facture_origine_id: str = "") -> str:
    """Crée la facture en statut BROUILLON. Aucun impact immédiat sur les stocks."""
    type_doc = "FactureAvoir" if is_avoir else "FactureClient"
    facture_id = generer_numero_facture_legal(type_doc)
    date_jour = get_local_now().strftime("%Y-%m-%d")

    totaux = calculer_montants_facture(panier, remise_globale, paiement_especes)

    montant_ht = totaux["net_a_payer"]
    montant_tva = totaux["total_tva"]
    montant_ttc = totaux["total_ttc"]
    timbre_fiscal = totaux["timbre_fiscal"]
    taux_tva = 0.19

    if is_avoir:
        montant_ht, montant_tva, montant_ttc = -montant_ht, -montant_tva, -montant_ttc

    data_facture = {
        "facture_id": facture_id, "commande_vente_id": "", "client_id": client_id,
        "date": date_jour, "montant_ht": montant_ht, "taux_tva": taux_tva,
        "montant_tva": montant_tva, "montant_ttc": montant_ttc, "montant_paye": 0.0,
        "statut": "BROUILLON", "date_echeance": str(date_echeance),
        "montant_timbre": timbre_fiscal, "type_facture": type_doc,
        "facture_origine_id": facture_origine_id, "remise_globale": remise_globale
    }

    lignes_a_inserer = []
    for item in panier:
        ligne_id = generate_technical_id("LFA")
        lignes_a_inserer.append({
            "ligne_facture_id": ligne_id, "facture_id": facture_id, "sku_id": item["sku_id"],
            "quantite": item["quantite"], "prix_unitaire": item["prix_unitaire"],
            "remise_ligne": item.get("remise", 0.0), "total_ligne_ht": item.get("total_ht", 0.0)
        })

    insert_hybrid("factures", data_facture)
    for ligne in lignes_a_inserer:
        insert_hybrid("lignes_facture", ligne)

    return facture_id


def valider_facture(facture_id: str):
    """Verrouille la facture et met à jour son statut."""
    lignes = get_lignes_facture(facture_id)
    df_factures = get_factures()

    if df_factures.empty or facture_id not in df_factures["facture_id"].values:
        raise ValueError("Facture introuvable.")

    facture_row = df_factures[df_factures["facture_id"] == facture_id].iloc[0]
    is_avoir = (facture_row.get("type_facture") == "FactureAvoir")

    if not is_avoir:
        df_stocks = pd.DataFrame(fetch_data("stock_actuel_pf"))
        if not df_stocks.empty:
            df_stocks = df_stocks.set_index("sku_id")

        for ligne in lignes:
            sku = ligne["sku_id"]
            qte_demandee = float(ligne["quantite"])

            if df_stocks.empty or sku not in df_stocks.index:
                raise ValueError(f"L'article {sku} est introuvable en stock.")

            qte_dispo = float(df_stocks.loc[sku, "quantite_disponible"])
            if qte_dispo < qte_demandee:
                raise ValueError(f"Stock insuffisant pour {sku}. Demandé : {qte_demandee}, Disponible : {qte_dispo}.")

    update_hybrid("factures", "facture_id", facture_id, {"statut": "VALIDE"})


def creer_bon_livraison(commande_vente_id: str, transporteur: str, zone: str, items_livraison: list) -> str:
    """
    Génère un Bon de Livraison (BL), enregistre les lignes d'expédition avec traçabilité du lot,
    et déduit les produits finis des stocks.
    """
    df_bl = get_bons_livraison()
    exist_ids = df_bl["bl_id"].tolist() if not df_bl.empty and "bl_id" in df_bl.columns else []
    bl_id = generate_unique_id("BL", exist_ids)
    date_jour = get_local_now().strftime("%Y-%m-%d")

    data_bl = {
        "bl_id": bl_id,
        "commande_vente_id": commande_vente_id,
        "date": date_jour,
        "transporteur": transporteur,
        "zone": zone,
        "statut": "EXPEDIE"
    }
    insert_hybrid("bons_livraison", data_bl)

    for item in items_livraison:
        sku_id = item["sku_id"]
        qte_livree = float(item["quantite_livree"])
        lot_id = item.get("lot_id", "DEFAUT")

        if qte_livree > 0:
            enregistrer_sortie_pf(sku_id=sku_id, quantite=qte_livree, reference=f"BL {bl_id}")

            ligne_bl_id = generate_technical_id("LBL")
            data_ligne_bl = {
                "ligne_bl_id": ligne_bl_id,
                "bl_id": bl_id,
                "sku_id": sku_id,
                "quantite_livree": qte_livree,
                "lot_id": lot_id
            }
            insert_hybrid("lignes_bons_livraison", data_ligne_bl)

    return bl_id


def annuler_facture(facture_id: str):
    """Annule la facture et réinjecte les articles en stock."""
    lignes = get_lignes_facture(facture_id)
    df_factures = get_factures()

    facture_row = df_factures[df_factures["facture_id"] == facture_id].iloc[0]
    is_avoir = (facture_row.get("type_facture") == "FactureAvoir")

    if not is_avoir:
        for ligne in lignes:
            enregistrer_entree_pf(ligne["sku_id"], ligne["quantite"], facture_id)

    update_hybrid("factures", "facture_id", facture_id, {"statut": "ANNULE"})