"""
Logique métier du module Comptabilité & Finances.
Gère les flux de trésorerie, les comptes, les règlements, le lettrage et la génération du Grand Livre.
Conforme au schéma officiel docs/schema_donnees.md.
Lecture Supabase, Écriture hybride (Supabase + Google Sheets).
"""
import pandas as pd
from core.db_service import fetch_data, insert_hybrid, update_hybrid
from core.utils import generate_technical_id, get_local_now

def get_comptes() -> pd.DataFrame:
    """Récupère la liste des comptes et caisses."""
    return pd.DataFrame(fetch_data("comptes"))

def get_reglements() -> pd.DataFrame:
    """Récupère l'historique de tous les flux financiers."""
    return pd.DataFrame(fetch_data("reglements"))

def get_lettrages() -> pd.DataFrame:
    """Récupère l'historique des lettrages (liaisons Règlements <-> Factures)."""
    return pd.DataFrame(fetch_data("lettrage"))

def get_ecritures_comptables() -> pd.DataFrame:
    """Récupère le Grand Livre comptable."""
    return pd.DataFrame(fetch_data("ecritures_comptables"))

def creer_compte(nom_compte: str, type_compte: str, numero_compte: str, solde_initial: float) -> str:
    """Crée un nouveau compte bancaire ou une caisse."""
    compte_id = generate_technical_id("CPT")

    data_compte = {
        "compte_id": compte_id, "nom_compte": nom_compte, "type_compte": type_compte,
        "numero_compte": numero_compte, "solde_initial": solde_initial, "statut": "OUI"
    }

    insert_hybrid("comptes", data_compte)
    return compte_id

def enregistrer_reglement(date_reglement: str, type_flux: str, partenaire_id: str, compte_id: str, mode_paiement: str, reference_trace: str, montant_total: float) -> str:
    """
    Enregistre un flux financier (Encaissement/Décaissement) et génère
    automatiquement l'écriture comptable correspondante dans ecritures_comptables.
    """
    reglement_id = generate_technical_id("REGF")

    data_reg = {
        "reglement_id": reglement_id, "date_reglement": date_reglement, "type_flux": type_flux,
        "partenaire_id": partenaire_id, "compte_id": compte_id, "mode_paiement": mode_paiement,
        "reference_trace": reference_trace, "montant_total": montant_total, "montant_alloue": 0.0,
        "statut": "VALIDE"
    }
    insert_hybrid("reglements", data_reg)

    # --- Génération automatique de l'écriture comptable (Grand Livre) ---
    ecriture_id = generate_technical_id("ECR")
    is_encaissement = (type_flux == "ENCAISSEMENT")

    data_ecriture = {
        "ecriture_id": ecriture_id,
        "date_ecriture": date_reglement,
        "compte_id": compte_id,
        "document_source_id": reglement_id,
        "libelle": f"{type_flux} - {mode_paiement} ({partenaire_id})",
        "debit": montant_total if is_encaissement else 0.0,
        "credit": 0.0 if is_encaissement else montant_total,
        "lettrage_id": ""
    }
    insert_hybrid("ecritures_comptables", data_ecriture)

    return reglement_id

def enregistrer_lettrage(reglement_id: str, document_id: str, type_document: str, montant_applique: float):
    """
    Lie un règlement à une facture (Client ou Fournisseur), met à jour le montant alloué du règlement,
    actualise le statut du document financier et marque les écritures comptables.
    """
    if montant_applique <= 0:
        raise ValueError("Le montant appliqué doit être supérieur à zéro.")

    df_reg = get_reglements()
    if df_reg.empty or "reglement_id" not in df_reg.columns:
        raise ValueError("Erreur de base de données (Règlements).")

    reg_row = df_reg[df_reg["reglement_id"] == reglement_id]
    if reg_row.empty:
        raise ValueError(f"Règlement {reglement_id} introuvable.")

    montant_total = float(reg_row.iloc[0].get("montant_total", 0))
    montant_alloue = float(reg_row.iloc[0].get("montant_alloue", 0))

    if (montant_alloue + montant_applique) > montant_total:
        raise ValueError(f"Le montant appliqué dépasse le solde restant du règlement (Solde restant : {montant_total - montant_alloue:,.2f} DZD).")

    lettrage_id = generate_technical_id("LET")
    date_jour = get_local_now().strftime("%Y-%m-%d")

    # 1. Traitement Factures Clients
    if type_document == "FactureClient":
        df_fac = pd.DataFrame(fetch_data("factures"))
        fac_row = df_fac[df_fac["facture_id"] == document_id]
        if not fac_row.empty:
            m_ttc = float(fac_row.iloc[0].get("montant_ttc", 0))
            m_paye = float(fac_row.iloc[0].get("montant_paye", 0))
            nouveau_paye = m_paye + montant_applique
            nouveau_statut = "PAYEE" if nouveau_paye >= (m_ttc - 1.0) else "PARTIELLE"

            update_hybrid("factures", "facture_id", document_id, {
                "montant_paye": nouveau_paye,
                "statut": nouveau_statut
            })

    # 2. Traitement Factures Fournisseurs
    elif type_document == "FactureFournisseur":
        df_ff = pd.DataFrame(fetch_data("factures_fournisseurs"))
        ff_row = df_ff[df_ff["facture_fournisseur_id"] == document_id]
        if not ff_row.empty:
            m_ttc = float(ff_row.iloc[0].get("montant_ttc", 0))
            m_paye = float(ff_row.iloc[0].get("statut_paiement", 0) if str(ff_row.iloc[0].get("statut_paiement", "")).replace(".","").isdigit() else 0)
            nouveau_paye = m_paye + montant_applique
            nouveau_statut = "PAYEE" if nouveau_paye >= (m_ttc - 1.0) else "PARTIELLE"

            update_hybrid("factures_fournisseurs", "facture_fournisseur_id", document_id, {
                "statut_paiement": nouveau_statut
            })

    # 3. Mise à jour du règlement & enregistrement du lettrage
    update_hybrid("reglements", "reglement_id", reglement_id, {
        "montant_alloue": montant_alloue + montant_applique
    })

    data_lettrage = {
        "lettrage_id": lettrage_id,
        "date": date_jour,
        "reglement_id": reglement_id,
        "document_id": document_id,
        "type_document": type_document,
        "montant_applique": montant_applique
    }
    insert_hybrid("lettrage", data_lettrage)