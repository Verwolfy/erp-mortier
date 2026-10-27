"""
Logique métier de l'Administration : Clients, Fournisseurs, MP, Produits, SKU, Utilisateurs et Permissions.
Hybride : Lecture sur Supabase, Écriture Supabase + Backup Google Sheets.
Respect strict du schéma docs/schema_reference.md.
"""
import pandas as pd
import uuid
import streamlit as st
from core.db_service import fetch_data, insert_hybrid, update_hybrid, get_supabase_client
from modules.auth.service import hash_password
from core.utils import generate_unique_id
from core.security_service import (
    require_security_manager, create_user_secure, add_permission_secure,
)

# Petit mapping local uniquement pour faire le lien entre l'UI et la lecture
READ_MAPPING = {
    "Fournisseurs": "fournisseurs",
    "MatieresPremieres": "matieres_premieres",
    "Produits": "produits",
    "SkuConditionnement": "sku_conditionnement",
    "Clients": "clients"
}

# Les champs techniques structurants ne sont pas modifiables dans le tableau
# générique : ils nécessitent un processus métier dédié et audité.
EDITABLE_FIELDS = {
    "Fournisseurs": frozenset({
        "nom", "categorie", "type_entreprise", "adresse", "gps", "pays",
        "wilaya", "rc", "nif", "nis", "nom_contact", "poste_contact",
        "email_contact", "mobile_contact", "email_entreprise", "site_web",
        "telephone_fixe", "delai_appro_jours", "actif",
    }),
    "MatieresPremieres": frozenset({
        "nom", "categorie_mp", "origine_pays", "duree_peremption_jours",
        "fournisseurs_ids", "stock_mini", "stock_maxi", "hs_code",
        "taux_dedouanement", "lien_fiche_technique", "lien_fiche_securite",
        "actif",
    }),
    "Produits": frozenset({"nom", "categorie_pf", "actif"}),
    "SkuConditionnement": frozenset({"format", "prix_vente_defaut", "actif"}),
    "Clients": frozenset({
        "nom", "categorie_client", "type_client", "adresse", "gps", "pays",
        "wilaya", "rc", "nif", "nis", "nom_contact", "poste_contact",
        "email_contact", "mobile_contact", "email_entreprise", "site_web",
        "telephone_fixe", "commercial_id", "actif",
    }),
}
PRIMARY_KEYS = {
    "Fournisseurs": "fournisseur_id",
    "MatieresPremieres": "mp_id",
    "Produits": "pf_id",
    "SkuConditionnement": "sku_id",
    "Clients": "client_id",
}

def _confirmed(result: object, operation: str) -> None:
    """Ne jamais annoncer un succès quand la réponse Supabase est absente."""
    if not isinstance(result, list) or len(result) != 1 or not isinstance(result[0], dict):
        raise RuntimeError(f"{operation} non confirmée dans Supabase ; vérifier l'état avant réessai")


def get_dataframe(sheet_name: str, only_active=False) -> pd.DataFrame:
    """Récupère les données depuis Supabase (SQL) pour une rapidité maximale."""
    table_name = READ_MAPPING.get(sheet_name)
    if not table_name:
        return pd.DataFrame()

    data = fetch_data(table_name)
    df = pd.DataFrame(data)

    if only_active and not df.empty and "actif" in df.columns:
        df = df[df["actif"] == "OUI"]
    return df

def sauvegarder_modifications(sheet_name: str, id_col: str,
                             df_original: pd.DataFrame, changes: dict) -> bool:
    """Modifie au plus une ligne, après contrôle strict des colonnes.

    Multi-lignes refusées jusqu'à une RPC PostgreSQL véritablement atomique.
    Une écriture confirmée sur Supabase n'implique PAS la réussite de Sheets.
    """
    table_name = READ_MAPPING.get(sheet_name)
    if table_name is None or id_col != PRIMARY_KEYS.get(sheet_name):
        raise ValueError("Référentiel ou identifiant non autorisé")
    if not isinstance(changes, dict) or len(changes) != 1:
        raise ValueError("Enregistrer une seule ligne à la fois (pas de transaction multi-lignes)")
    row_key, columns = next(iter(changes.items()))
    if not isinstance(columns, dict) or not columns:
        raise ValueError("Aucune modification valide")
    if set(columns) - EDITABLE_FIELDS[sheet_name]:
        raise ValueError("Une colonne technique protégée ne peut pas être modifiée ici")
    try:
        row_idx = int(row_key)
        if isinstance(row_key, bool) or str(row_idx) != str(row_key):
            raise ValueError
    except (ValueError, TypeError) as exc:
        raise ValueError("Indice de ligne invalide") from exc
    if row_idx < 0 or row_idx >= len(df_original) or id_col not in df_original.columns:
        raise ValueError("Ligne ou identifiant introuvable")
    target_id = df_original.iloc[row_idx][id_col]
    if not isinstance(target_id, str) or not target_id.strip():
        raise ValueError("Identifiant de ligne invalide")
    # Valider tout AVANT l'écriture. Ne pas masquer l'échec de Supabase.
    updates = {col: str(value) for col, value in columns.items()}
    if "actif" in updates:
        value = updates["actif"].strip().upper()
        if value not in {"OUI", "NON"}:
            raise ValueError("Statut actif invalide : OUI ou NON")
        updates["actif"] = value
    result = update_hybrid(table_name, id_col, target_id, updates)
    _confirmed(result, "Modification")
    if result[0].get(id_col) != target_id:
        raise RuntimeError("Ligne modifiée non vérifiable ; contrôler Supabase")
    return True

# --- FOURNISSEURS, MP, PRODUITS, SKU, CLIENTS ---
def add_fournisseur(data: dict):
    df = get_dataframe("Fournisseurs")
    exist_ids = df["fournisseur_id"].tolist() if not df.empty else []
    data["fournisseur_id"] = generate_unique_id("FRN", exist_ids)
    data["actif"] = "OUI"
    _confirmed(insert_hybrid("fournisseurs", data), "Création fournisseur")
    return data["fournisseur_id"]

def add_matiere_premiere(data: dict):
    df = get_dataframe("MatieresPremieres")
    exist_ids = df["mp_id"].tolist() if not df.empty else []
    data["mp_id"] = generate_unique_id("MP", exist_ids)
    data["actif"] = "OUI"
    data["cmp_actuel"] = 0.0
    _confirmed(insert_hybrid("matieres_premieres", data), "Création matière première")
    return data["mp_id"]

def add_produit(data: dict):
    df = get_dataframe("Produits")
    exist_ids = df["pf_id"].tolist() if not df.empty else []
    data["pf_id"] = generate_unique_id("PF", exist_ids)
    data["actif"] = "OUI"
    _confirmed(insert_hybrid("produits", data), "Création produit")
    return data["pf_id"]

def add_sku(data: dict):
    df = get_dataframe("SkuConditionnement")
    exist_ids = df["sku_id"].tolist() if not df.empty else []
    data["sku_id"] = generate_unique_id("SKU", exist_ids)
    data["actif"] = "OUI"
    _confirmed(insert_hybrid("sku_conditionnement", data), "Création SKU")
    return data["sku_id"]

def add_client(data: dict):
    df = get_dataframe("Clients")
    exist_ids = df["client_id"].tolist() if not df.empty else []
    data["client_id"] = generate_unique_id("CLI", exist_ids)
    data["actif"] = "OUI"
    _confirmed(insert_hybrid("clients", data), "Création client")
    return data["client_id"]

# ==========================================
# GESTION DES UTILISATEURS ET PERMISSIONS
# ==========================================

def get_users() -> pd.DataFrame:
    """Récupère la liste des utilisateurs seulement si habilité."""
    require_security_manager()
    # Projeter explicitement les colonnes non sensibles, sans télécharger hash_mdp.
    response = (get_supabase_client().table("users")
                .select("user_id,nom,login,role,actif").execute())
    if not isinstance(response.data, list):
        raise RuntimeError("Annuaire utilisateurs indisponible")
    return pd.DataFrame(response.data)

def add_user(nom: str, login: str, mot_de_passe_clair: str, role: str):
    """Crée un utilisateur, hache son mot de passe et l'enregistre."""
    require_security_manager()
    nouveau_id = "USR-" + uuid.uuid4().hex[:16].upper()

    # Sécurisation du mot de passe
    hash_mdp = hash_password(mot_de_passe_clair)

    # Respect du schéma : user_id, nom, login, hash_mdp, role, actif
    data_user = {
        "user_id": nouveau_id,
        "nom": nom,
        "login": login,
        "hash_mdp": hash_mdp,
        "role": role,
        "actif": "OUI"
    }

    return create_user_secure(
        data_user["user_id"], data_user["nom"], data_user["login"],
        data_user["hash_mdp"], data_user["role"],
    )

def get_permissions() -> pd.DataFrame:
    """Récupère la matrice des permissions."""
    require_security_manager()
    response = (get_supabase_client().table("permissions")
                .select("role,module,lecture,ecriture").execute())
    if not isinstance(response.data, list):
        raise RuntimeError("Matrice des permissions indisponible")
    return pd.DataFrame(response.data)

def add_permission(role: str, module: str, lecture: str, ecriture: str):
    """Associe des droits de lecture/écriture à un rôle pour un module précis."""
    # Respect du schéma : role, module, lecture, ecriture
    data_perm = {
        "role": role,
        "module": module,
        "lecture": lecture,
        "ecriture": ecriture
    }

    return add_permission_secure(
        data_perm["role"], data_perm["module"],
        data_perm["lecture"], data_perm["ecriture"],
    )

def get_audit_logs() -> pd.DataFrame:
    """Récupère l'historique des actions (logs) classé du plus récent au plus ancien."""
    require_security_manager()
    response = (get_supabase_client().table("audit_trail")
                .select("audit_id,timestamp,user_id,module,action,detail").execute())
    if not isinstance(response.data, list):
        raise RuntimeError("Piste d'audit indisponible")
    df = pd.DataFrame(response.data)
    if not df.empty and "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], format="mixed", utc=True, errors="coerce")
        df = df.sort_values(by="timestamp", ascending=False)
    return df