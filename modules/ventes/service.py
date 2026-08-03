"""
Logique métier du module Ventes.
Fusion du module Facturation.
Gère les Factures, Avoirs, LignesFacture et Règlements selon docs/schema_reference.md.
Lecture Supabase, Écriture hybride (Supabase + Google Sheets).
"""
import time
import pandas as pd
import streamlit as st
from core.db_service import fetch_data, insert_hybrid, update_hybrid, get_supabase_client
from core.utils import generate_technical_id, get_local_now
from modules.stocks.service import enregistrer_sortie_pf

try:
    from num2words import num2words
except ImportError:
    num2words = None


def get_factures() -> pd.DataFrame:
    return pd.DataFrame(fetch_data("factures"))


def generer_numero_facture_legal(type_document: str) -> str:
    """Génère un numéro séquentiel strict pour FactureClient ou FactureAvoir via Supabase RPC."""
    # 1. On récupère le préfixe et l'année (lecture simple)
    df_compteurs = pd.DataFrame(fetch_data("compteurs"))
    if df_compteurs.empty or type_document not in df_compteurs["type_document"].values:
        raise ValueError(f"Le compteur {type_document} n'est pas initialisé dans la base de données.")

    row = df_compteurs[df_compteurs["type_document"] == type_document].iloc[0]
    prefixe = str(row.get("prefixe", "FAC"))
    annee = str(row.get("annee", get_local_now().year))

    # 2. Appel de la fonction SQL atomique (zéro risque de doublon)
    try:
        supabase = get_supabase_client()
        response = supabase.rpc("increment_compteur", {"p_type_document": type_document}).execute()
        nouveau_numero = response.data

        # 3. Sauvegarde miroir dans Google Sheets
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
        lettres = f"{montant_ttc_final:,.2f} Dinars Algériens (Installez 'num2words')"

    return {
        "total_ht": round(montant_ht_brut, 2),
        "total_remise": round(total_remise, 2),
        "net_a_payer": round(net_a_payer_ht, 2),
        "total_tva": round(montant_tva, 2),
        "timbre_fiscal": round(timbre_fiscal, 2),
        "total_ttc": round(montant_ttc_final, 2),
        "montant_lettres": lettres.capitalize()
    }


def create_facture(client_id: str, date_echeance: str, panier: list, remise_globale: float = 0.0, paiement_especes: bool = False, is_avoir: bool = False, facture_origine_id: str = "") -> str:
    """
    Crée une facture ou un avoir.
    Déclenche la sortie de stock si c'est une vente normale (avec vérification atomique).
    Persiste toutes les colonnes selon le schéma de référence.
    """
    type_doc = "FactureAvoir" if is_avoir else "FactureClient"
    facture_id = generer_numero_facture_legal(type_doc)
    date_jour = get_local_now().strftime("%Y-%m-%d")

    # 1. Déduction des stocks physiques (Uniquement pour les factures, pas les avoirs)
    if not is_avoir:
        # --- PASSE 1 : Vérification des disponibilités globales ---
        df_stocks = pd.DataFrame(fetch_data("stocks_pf"))
        if not df_stocks.empty:
            df_stocks = df_stocks.set_index("sku_id")

        for item in panier:
            sku = item["sku_id"]
            qte_demandee = float(item["quantite"])

            if df_stocks.empty or sku not in df_stocks.index:
                raise ValueError(f"Erreur d'atomicité : L'article {sku} est introuvable en stock. Facturation annulée.")

            qte_dispo = float(df_stocks.loc[sku, "quantite_actuelle"])
            if qte_dispo < qte_demandee:
                raise ValueError(f"Erreur d'atomicité : Stock insuffisant pour {sku}. Demandé : {qte_demandee}, Disponible : {qte_dispo}. Facturation annulée.")

        # --- PASSE 2 : Déduction effective une fois tout le panier validé ---
        for item in panier:
            enregistrer_sortie_pf(item["sku_id"], item["quantite"], facture_id)

    # 2. Calculs financiers
    totaux = calculer_montants_facture(panier, remise_globale, paiement_especes)

    montant_ht = totaux["net_a_payer"]
    montant_tva = totaux["total_tva"]
    montant_ttc = totaux["total_ttc"]
    timbre_fiscal = totaux["timbre_fiscal"]
    taux_tva = 0.19

    if is_avoir:
        montant_ht, montant_tva, montant_ttc = -montant_ht, -montant_tva, -montant_ttc

    # 3. Préparation des données Facture
    data_facture = {
        "facture_id": facture_id, "commande_vente_id": "", "client_id": client_id,
        "date": date_jour, "montant_ht": montant_ht, "taux_tva": taux_tva,
        "montant_tva": montant_tva, "montant_ttc": montant_ttc, "montant_paye": 0.0,
        "statut": "VALIDE" if is_avoir else "EN_ATTENTE", "date_echeance": str(date_echeance),
        "montant_timbre": timbre_fiscal, "type_facture": type_doc,
        "facture_origine_id": facture_origine_id, "remise_globale": remise_globale
    }

    # 4. Préparation des LignesFacture
    lignes_a_inserer = []

    for item in panier:
        ligne_id = generate_technical_id("LFA")
        lignes_a_inserer.append({
            "ligne_facture_id": ligne_id, "facture_id": facture_id, "sku_id": item["sku_id"],
            "quantite": item["quantite"], "prix_unitaire": item["prix_unitaire"],
            "remise_ligne": item.get("remise", 0.0), "total_ligne_ht": item.get("total_ht", 0.0)
        })

    # 5. Écriture finale
    insert_hybrid("factures", data_facture)
    for ligne in lignes_a_inserer:
        insert_hybrid("lignes_facture", ligne)

    return facture_id