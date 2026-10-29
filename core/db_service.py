"""
Service de base de données hybride (Supabase + Google Sheets).
Lit depuis Supabase (SQL). Écrit dans Supabase ET Google Sheets (Dual-Write).
Le schéma est centralisé ici pour éviter les erreurs de frappe.
Intègre une piste d'audit automatique ET UN CONTRÔLE DE DROITS SERVEUR.
"""
import hashlib
import logging
import re
from typing import Any, Optional

import streamlit as st
from supabase import create_client, Client
from core.environment_guard import policy_from_streamlit, require_supabase_target
from core.sheets_service import append_rows_batch, update_multiple_cells_by_id
from core.logger import log_error
from config.roles import has_permission
from core.utils import get_local_now

# ==========================================
# DICTIONNAIRE CENTRAL DU SCHÉMA DE DONNÉES
# Strictement conforme à docs/schema_donnees.md
# ==========================================
SCHEMA_CONFIG = {
    # --- REFERENTIELS ---
    "fournisseurs": {"module": "referentiels", "sheet": "Fournisseurs", "cols": ["fournisseur_id", "nom", "categorie", "type_entreprise", "adresse", "gps", "pays", "wilaya", "rc", "nif", "nis", "nom_contact", "poste_contact", "email_contact", "mobile_contact", "email_entreprise", "site_web", "telephone_fixe", "delai_appro_jours", "actif"]},
    "matieres_premieres": {"module": "referentiels", "sheet": "MatieresPremieres", "cols": ["mp_id", "nom", "categorie_mp", "unite_stock", "origine_pays", "duree_peremption_jours", "fournisseurs_ids", "actif", "type_emballage", "poids_net", "cmp_actuel", "stock_mini", "stock_maxi", "hs_code", "taux_dedouanement", "lien_fiche_technique", "lien_fiche_securite"]},
    "produits": {"module": "referentiels", "sheet": "Produits", "cols": ["pf_id", "nom", "categorie_pf", "recette_id", "unite_production", "actif"]},
    "sku_conditionnement": {"module": "referentiels", "sheet": "SkuConditionnement", "cols": ["sku_id", "pf_id", "format", "emballage_mp_id", "poids_net", "unite_vente", "facteur_conversion", "prix_vente_defaut", "actif"]},
    "clients": {"module": "referentiels", "sheet": "Clients", "cols": ["client_id", "nom", "categorie_client", "type_client", "adresse", "gps", "pays", "wilaya", "rc", "nif", "nis", "nom_contact", "poste_contact", "email_contact", "mobile_contact", "email_entreprise", "site_web", "telephone_fixe", "commercial_id", "actif"]},
    "contrats": {"module": "referentiels", "sheet": "Contrats", "cols": ["contrat_id", "client_id", "date_debut", "date_fin", "grille_tarifaire_id", "renouvellement_auto", "conditions", "actif"]},
    "grilles_tarifaires": {"module": "referentiels", "sheet": "GrillesTarifaires", "cols": ["grille_id", "client_id_ou_categorie", "sku_id", "prix_negocie", "remise_pct", "date_debut", "date_fin"]},
    "parametres": {"module": "referentiels", "sheet": "Parametres", "cols": ["cle", "valeur"]},
    "users": {"module": "referentiels", "sheet": "Users", "cols": ["user_id", "nom", "login", "hash_mdp", "role", "actif"]},
    "permissions": {"module": "referentiels", "sheet": "Permissions", "cols": ["role", "module", "lecture", "ecriture"]},
    "compteurs": {"module": "referentiels", "sheet": "Compteurs", "cols": ["type_document", "prefixe", "annee", "dernier_numero"]},
    "listes_reference": {"module": "referentiels", "sheet": "ListesReference", "cols": ["liste_code", "parent_code", "valeur_code", "valeur_libelle", "ordre", "actif"]},

    # --- ACHATS ---
    "commandes_achats": {"module": "achats", "sheet": "CommandesAchats", "cols": ["commande_achat_id", "date_commande", "fournisseur_id", "type_achat", "devise", "taux_change", "montant_total_devise", "montant_total_local", "mode_paiement", "delai_paiement", "date_voulue", "statut"]},
    "lignes_achats": {"module": "achats", "sheet": "LignesAchats", "cols": ["ligne_achat_id", "commande_achat_id", "mp_id", "unite_cond", "qte_cond", "qte_totale", "prix_unitaire", "total_devise"]},
    "appels_offres": {"module": "achats", "sheet": "AppelsOffres", "cols": ["ao_id", "besoin_description", "mp_id", "date_limite", "statut"]},
    "reponses_appels_offres": {"module": "achats", "sheet": "ReponsesAppelsOffres", "cols": ["reponse_ao_id", "ao_id", "fournisseur_id", "prix_propose", "delai_propose", "date_reponse"]},
    "bons_reception": {"module": "achats", "sheet": "BonsReception", "cols": ["bon_reception_id", "commande_achat_id", "date_reception", "controle_conformite", "remarques"]},
    "lignes_bons_reception": {"module": "achats", "sheet": "LignesBonsReception", "cols": ["ligne_br_id", "bon_reception_id", "mp_id", "quantite_recue", "lot_attribue_id"]},
    "factures_fournisseurs": {"module": "achats", "sheet": "FacturesFournisseurs", "cols": ["facture_fournisseur_id", "commande_achat_id", "fournisseur_id", "reference_facture_fournisseur", "date", "montant_ht", "taux_tva", "montant_tva", "montant_ttc", "statut_paiement"]},
    "lignes_factures_fournisseurs": {"module": "achats", "sheet": "LignesFacturesFournisseurs", "cols": ["ligne_ff_id", "facture_fournisseur_id", "mp_id_ou_service", "quantite", "prix_unitaire", "taux_tva", "total_ht"]},

    # --- STOCKS ---
    "mouvements": {"module": "stocks", "sheet": "Mouvements", "cols": ["mouvement_id", "date", "type_mouvement", "mp_id", "quantite", "reference", "lot_id", "prix_entree"]},
    "mouvements_pf": {"module": "stocks", "sheet": "MouvementsPf", "cols": ["mouvement_pf_id", "date", "type_mouvement", "sku_id", "quantite", "reference", "lot_id", "cout_unitaire"]},
    "lots": {"module": "stocks", "sheet": "Lots", "cols": ["lot_id", "item_id", "type_item", "date_creation", "date_peremption", "quantite_initiale", "quantite_restante", "statut"]},
    "stock_actuel": {"module": "stocks", "sheet": "StockActuel", "cols": ["mp_id", "quantite_disponible", "cmp_actuel", "derniere_maj"]},
    "stock_actuel_pf": {"module": "stocks", "sheet": "StockActuelPf", "cols": ["sku_id", "quantite_disponible", "cout_revient", "derniere_maj"]},

    # --- PRODUCTION ---
    "recettes": {"module": "production", "sheet": "Recettes", "cols": ["recette_id", "pf_id", "version", "rendement_unite", "instructions", "date_effet", "actif"]},
    "lignes_recette": {"module": "production", "sheet": "LignesRecette", "cols": ["ligne_recette_id", "recette_id", "mp_id", "quantite_par_unite"]},
    "ordres_fabrication": {"module": "production", "sheet": "OrdresFabrication", "cols": ["of_id", "pf_id", "recette_id", "sku_id", "quantite_prevue", "quantite_produite", "date_planification", "date_debut", "date_fin", "statut", "cout_total", "notes"]},
    "consommations_of": {"module": "production", "sheet": "ConsommationsOf", "cols": ["consommation_id", "of_id", "mp_id", "lot_id", "quantite_consommee"]},
    "controle_qualite": {"module": "production", "sheet": "ControleQualite", "cols": ["qc_id", "of_id", "date", "conforme", "remarques", "controleur"]},

    # --- VENTES ---
    "devis": {"module": "ventes", "sheet": "Devis", "cols": ["devis_id", "client_id", "date", "validite", "statut", "commercial_id"]},
    "lignes_devis": {"module": "ventes", "sheet": "LignesDevis", "cols": ["ligne_devis_id", "devis_id", "sku_id", "quantite", "prix_unitaire", "remise_pct"]},
    "commandes_ventes": {"module": "ventes", "sheet": "CommandesVentes", "cols": ["commande_vente_id", "devis_id", "client_id", "date", "statut"]},
    "lignes_commande_ventes": {"module": "ventes", "sheet": "LignesCommandeVentes", "cols": ["ligne_commande_vente_id", "commande_vente_id", "sku_id", "quantite", "prix_unitaire"]},
    "bons_livraison": {"module": "ventes", "sheet": "BonsLivraison", "cols": ["bl_id", "commande_vente_id", "date", "transporteur", "zone", "statut"]},
    "lignes_bons_livraison": {"module": "ventes", "sheet": "LignesBonsLivraison", "cols": ["ligne_bl_id", "bl_id", "sku_id", "quantite_livree", "lot_id"]},
    "factures": {"module": "ventes", "sheet": "Factures", "cols": ["facture_id", "commande_vente_id", "client_id", "date", "montant_ht", "taux_tva", "montant_tva", "montant_ttc", "montant_paye", "statut", "date_echeance", "montant_timbre", "type_facture", "facture_origine_id", "remise_globale"]},
    "lignes_facture": {"module": "ventes", "sheet": "LignesFacture", "cols": ["ligne_facture_id", "facture_id", "sku_id", "quantite", "prix_unitaire", "remise_ligne", "total_ligne_ht"]},

    # --- FINANCE ---
    "comptes": {"module": "finance", "sheet": "Comptes", "cols": ["compte_id", "nom_compte", "type_compte", "numero_compte", "solde_initial", "statut"]},
    "ecritures_comptables": {"module": "finance", "sheet": "EcrituresComptables", "cols": ["ecriture_id", "date_ecriture", "compte_id", "document_source_id", "libelle", "debit", "credit", "lettrage_id"]},
    "reglements": {"module": "finance", "sheet": "Reglements", "cols": ["reglement_id", "date_reglement", "type_flux", "partenaire_id", "compte_id", "mode_paiement", "reference_trace", "montant_total", "montant_alloue", "statut"]},
    "lettrage": {"module": "finance", "sheet": "Lettrage", "cols": ["lettrage_id", "date", "reglement_id", "document_id", "type_document", "montant_applique"]},
    # Accusés internes : consultation Finance uniquement, aucune écriture hybride.
    "erp_recus_internes": {"module": "finance", "sheet": None, "cols": [
        "recu_id", "reglement_id", "operation_id", "client_id", "date_reglement",
        "montant_encaisse", "mode_paiement", "reference_reglement",
        "statut", "timbre_statut", "cree_le"]},

    # --- CRM ---
    "interactions": {"module": "crm", "sheet": "Interactions", "cols": ["interaction_id", "client_id", "date_creation", "type_action", "notes", "date_rappel", "statut_rappel"]},
    "pipeline": {"module": "crm", "sheet": "Pipeline", "cols": ["opportunite_id", "prospect_nom", "contact", "statut", "commercial_id", "valeur_estimee", "probabilite_pct", "date_creation", "date_derniere_action"]},

    # --- RH ---
    "employes": {"module": "rh", "sheet": "Employes", "cols": ["employe_id", "nom", "poste", "service", "manager_id", "date_embauche", "actif"]},
    "demandes_conges": {"module": "rh", "sheet": "DemandesConges", "cols": ["demande_conge_id", "employe_id", "date_debut", "date_fin", "motif", "statut"]},
    "projets": {"module": "rh", "sheet": "Projets", "cols": ["projet_id", "nom", "client_id", "date_debut", "date_fin_prevue", "statut"]},
    "taches": {"module": "rh", "sheet": "Taches", "cols": ["tache_id", "projet_id", "assigne_a", "statut", "date_echeance"]},
    "feuilles_de_temps": {"module": "rh", "sheet": "FeuillesDeTemps", "cols": ["feuille_temps_id", "employe_id", "tache_id", "date", "heures"]},
    "fiches_de_paie": {"module": "rh", "sheet": "FichesDePaie", "cols": ["fiche_paie_id", "employe_id", "mois", "annee", "salaire_base", "primes", "retenues", "net_a_payer", "statut_paiement"]},

    # --- LOGS ---
    "audit_trail": {"module": "logs", "sheet": "AuditTrail", "cols": ["timestamp", "user_id", "module", "action", "detail"]},
    "erreurs": {"module": "logs", "sheet": "Erreurs", "cols": ["timestamp", "module", "message", "contexte"]},
    "logs": {"module": "logs", "sheet": "Logs", "cols": ["log_id", "date_action", "user_id", "action", "table_name", "details"]},
}

# Clés primaires absentes de la liste des colonnes synchronisées vers Sheets.
_EXTRA_COLUMNS = {
    "permissions": {"permission_id"},
    "listes_reference": {"id"},
    "audit_trail": {"audit_id"},
    "erreurs": {"erreur_id"},
}

# Aucune donnée de comptes ou d'autorisations n'est recopiée dans Sheets.
# Supabase est la source de vérité pour ces informations sensibles.
_NO_SHEETS_SYNC = frozenset({"users", "permissions", "audit_trail", "erreurs", "logs", "erp_recus_internes"})
_PRIMARY_KEY_OVERRIDES = {
    "permissions": "permission_id",
    "listes_reference": "id",
    "audit_trail": "audit_id",
    "erreurs": "erreur_id",
}
# Ecritures generiques: SEULEMENT les creations encore utilisees par les modules.
# Stocks, Achats, Ventes et Finance ecrivent exclusivement via les RPC atomiques.
# Recettes et OF planifies sont exclusivement crees par les RPC de migration 008.
_HYBRID_INSERT_TABLES = frozenset({
    "fournisseurs", "matieres_premieres", "produits", "sku_conditionnement",
    "clients", "listes_reference",
    "pipeline", "interactions", "employes", "demandes_conges",
})

# Mises a jour generiques: champs standards de l'editeur Administration,
# conformes a modules/admin/service.py (correctif ecf30a5).
_HYBRID_UPDATE_FIELDS = {
    "fournisseurs": frozenset({
        "nom", "categorie", "type_entreprise", "adresse", "gps", "pays",
        "wilaya", "rc", "nif", "nis", "nom_contact", "poste_contact",
        "email_contact", "mobile_contact", "email_entreprise", "site_web",
        "telephone_fixe", "delai_appro_jours", "actif",
    }),
    "matieres_premieres": frozenset({
        "nom", "categorie_mp", "origine_pays", "duree_peremption_jours",
        "fournisseurs_ids", "stock_mini", "stock_maxi", "hs_code",
        "taux_dedouanement", "lien_fiche_technique", "lien_fiche_securite", "actif",
    }),
    "produits": frozenset({"nom", "categorie_pf", "actif"}),
    "sku_conditionnement": frozenset({"format", "prix_vente_defaut", "actif"}),
    "clients": frozenset({
        "nom", "categorie_client", "type_client", "adresse", "gps", "pays",
        "wilaya", "rc", "nif", "nis", "nom_contact", "poste_contact",
        "email_contact", "mobile_contact", "email_entreprise", "site_web",
        "telephone_fixe", "commercial_id", "actif",
    }),
    "listes_reference": frozenset({"actif"}),
}
_HYBRID_UPDATE_PK = {
    "fournisseurs": "fournisseur_id",
    "matieres_premieres": "mp_id",
    "produits": "pf_id",
    "sku_conditionnement": "sku_id",
    "clients": "client_id",
    "listes_reference": "id",
}

_ADMIN_ROLES = frozenset({"ADMIN", "ADMINISTRATEUR", "SUPERADMIN"})
_ACTIVE_VALUES = frozenset({"oui", "o", "true", "1", "actif", "active", "yes", "y"})
_LOG = logging.getLogger(__name__)

# Les referentiels servent aussi les modules metier : acces explicites par table.
# Pas de droit general pour Dashboards (agregats a securiser separement).
_SHARED_READ_MODULES = {
    "fournisseurs": ("Administration", "Achats", "Finance"),
    "matieres_premieres": ("Administration", "Achats", "Stocks", "Production"),
    "produits": ("Administration", "Stocks", "Production", "Ventes"),
    "sku_conditionnement": ("Administration", "Stocks", "Production", "Ventes"),
    "clients": ("Administration", "Ventes", "CRM", "Finance"),
    "contrats": ("Administration", "Ventes", "CRM"),
    "grilles_tarifaires": ("Administration", "Ventes", "CRM"),
    "compteurs": ("Administration", "Ventes"),
    "listes_reference": ("Administration", "Achats", "Stocks",
                         "Production", "Ventes", "CRM", "Finance", "RH"),
}

# Les lectures generiques ne doivent jamais exposer les empreintes des mots de passe.
_READ_PROJECTIONS = {
    "users": "user_id,nom,login,role,actif",
    "erp_recus_internes": (
        "recu_id,reglement_id,client_id,date_reglement,montant_encaisse,"
        "mode_paiement,reference_reglement,statut,timbre_statut,cree_le"
    ),
}


def _known_columns(table_name: str) -> set[str]:
    config = SCHEMA_CONFIG.get(table_name)
    if config is None:
        raise ValueError(f"Table non référencée dans SCHEMA_CONFIG : {table_name!r}")
    return set(config["cols"]) | _EXTRA_COLUMNS.get(table_name, set())


def _check_write_columns(table_name: str, data: dict[str, Any]) -> None:
    if not isinstance(data, dict) or not data:
        raise ValueError("Les données à écrire doivent être un dictionnaire non vide.")
    invalid = set(data) - _known_columns(table_name)
    if invalid:
        raise ValueError(f"Colonnes non autorisées dans {table_name}: {sorted(invalid)}")


def _is_active(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in _ACTIVE_VALUES


def get_supabase_client() -> Client:
    """Vérifie l'environnement à chaque demande, sans client Auth partagé en cache.

    010-A-01 privilégie l'isolation des sessions sur la mise en cache. Les coûts
    de création du client devront être mesurés avant tout déploiement.
    """
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    require_supabase_target(policy_from_streamlit(st.secrets), url)
    return create_client(url, key)


def check_server_permission(table_name: str) -> bool:
    """Valide le compte et son rôle depuis la base avant toute écriture.

    L'identité est issue de la session Streamlit, mais le rôle n'est *jamais*
    considéré comme autoritaire tant que Supabase ne l'a pas confirmé.
    """
    if table_name not in SCHEMA_CONFIG:
        return False
    try:
        state = st.session_state
        if state.get("authenticated") is not True:
            return False
        session_user = state.get("user")
        if not isinstance(session_user, dict):
            return False
        user_id = session_user.get("user_id")
        if not isinstance(user_id, str) or not user_id.strip():
            return False

        response = (get_supabase_client().table("users")
                    .select("user_id,role,actif")
                    .eq("user_id", user_id).limit(1).execute())
        records = response.data or []
        if len(records) != 1:
            return False
        account = records[0]
        if not isinstance(account, dict) or account.get("user_id") != user_id:
            return False
        if not _is_active(account.get("actif")):
            return False
        role = str(account.get("role") or "").strip()
        if not role:
            return False

        if role.upper() in _ADMIN_ROLES:
            return True
        module = SCHEMA_CONFIG[table_name]["module"]
        module = "Administration" if module in ("referentiels", "logs") else module.capitalize()
        return has_permission(role, module, "ecriture") is True
    except Exception as exc:
        # Mode sécurité par défaut : en cas de panne de vérification, refuser.
        # Ne pas afficher la réponse API, qui peut contenir des informations sensibles.
        _LOG.warning("Vérification de droits impossible (%s)", type(exc).__name__)
        return False


def check_server_read_permission(table_name: str) -> bool:
    """Verifie a chaque lecture le compte Supabase actif et le droit RBAC frais.

    L'acces aux referentiels partages est limite aux modules explicitement
    listes ci-dessus ; une erreur reseau ou une matrice invalide refuse l'acces.
    """
    if table_name not in SCHEMA_CONFIG:
        return False
    try:
        state = st.session_state
        if state.get("authenticated") is not True:
            return False
        session_user = state.get("user")
        if not isinstance(session_user, dict):
            return False
        user_id = session_user.get("user_id")
        if not isinstance(user_id, str) or not user_id.strip():
            return False

        response = (get_supabase_client().table("users")
                    .select("user_id,role,actif")
                    .eq("user_id", user_id).limit(1).execute())
        records = response.data or []
        if len(records) != 1:
            return False
        account = records[0]
        if not isinstance(account, dict) or account.get("user_id") != user_id:
            return False
        if not _is_active(account.get("actif")):
            return False
        role = str(account.get("role") or "").strip()
        if not role:
            return False
        if role.upper() in _ADMIN_ROLES:
            return True

        modules = _SHARED_READ_MODULES.get(table_name)
        if modules is None:
            module = SCHEMA_CONFIG[table_name]["module"]
            modules = (("Administration",) if module in ("referentiels", "logs")
                       else (module.capitalize(),))
        return any(has_permission(role, module, "lecture") is True
                   for module in modules)
    except Exception as exc:
        _LOG.warning("Verification de droits de lecture impossible (%s)",
                     type(exc).__name__)
        return False


def _require_read_permission(table_name: str) -> None:
    if not check_server_read_permission(table_name):
        raise PermissionError(f"Droit de lecture refuse pour {table_name!r}")


def _read_projection(table_name: str) -> str:
    return _READ_PROJECTIONS.get(table_name, "*")


def _readable_columns(table_name: str) -> set[str]:
    projection = _READ_PROJECTIONS.get(table_name)
    return set(projection.split(",")) if projection else _known_columns(table_name)


def _audit_details(table_name: str, action: str, data: dict[str, Any],
                   *, id_col: Optional[str] = None, target_id: Any = None) -> str:
    """Audit de métadonnées, jamais de valeurs métier ou de mots de passe."""
    columns = ",".join(sorted(data))
    # L'ID est volontairement omis pour ne pas divulguer des données privées.
    return f"operation={action}; table={table_name}; colonnes=[{columns}]"[:1000]


def log_action(action: str, table_name: str, details: str) -> None:
    """Audit best-effort, en minimisant les données des appelants historiques."""
    try:
        user = st.session_state.get("user") if hasattr(st, "session_state") else None
        user_id = user.get("user_id", "SYSTEM") if isinstance(user, dict) else "SYSTEM"
        # Le texte libre historique peut contenir des secrets ou des données
        # personnelles. N'en stocker que l'empreinte non réversible, sauf pour
        # notre format structuré (noms de colonnes uniquement).
        raw = str(details)
        if re.fullmatch(r"operation=(INSERT|UPDATE); table=[a-z_]+; colonnes=\[[a-z0-9_,]*\]", raw):
            detail = raw[:1000]
        else:
            digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            detail = f"details_masques; sha256={digest}"
        get_supabase_client().table("audit_trail").insert({
            "timestamp": get_local_now().strftime("%Y-%m-%d %H:%M:%S"),
            "user_id": user_id,
            "module": table_name,
            "action": action,
            "detail": detail,
        }).execute()
    except Exception as exc:
        # L'échec d'audit n'annule PAS la transaction déjà validée en base.
        _LOG.warning("Écriture dans audit_trail impossible (%s)", type(exc).__name__)


def fetch_data(table_name: str) -> list:
    """Lecture historique (compatibilité). Attention : pagination Supabase non gérée."""
    _require_read_permission(table_name)
    try:
        response = (get_supabase_client().table(table_name)
                    .select(_read_projection(table_name)).execute())
        return response.data or []
    except Exception as exc:
        log_error(f"Erreur de lecture Supabase sur la table {table_name}", type(exc).__name__)
        return []


def fetch_data_filtered(table_name: str, filter_column: str, filter_value: str) -> list:
    """Filtre serveur, API conservée pour compatibilité avec les vues existantes."""
    _require_read_permission(table_name)
    if filter_column not in _readable_columns(table_name):
        raise ValueError(f"Colonne de filtre inconnue : {filter_column}")
    try:
        response = (get_supabase_client().table(table_name)
                    .select(_read_projection(table_name))
                    .eq(filter_column, filter_value).execute())
        return response.data or []
    except Exception as exc:
        log_error(f"Erreur de lecture filtrée Supabase sur {table_name}", type(exc).__name__)
        return []


def fetch_data_by_date_range(table_name: str, date_column: str,
                             start_date: str, end_date: str) -> list:
    """Filtre serveur par dates ; colonnes TEXT supposées ISO-8601 ordonnables."""
    _require_read_permission(table_name)
    if date_column not in _readable_columns(table_name):
        raise ValueError(f"Colonne de date inconnue : {date_column}")
    try:
        response = (get_supabase_client().table(table_name)
                    .select(_read_projection(table_name))
                    .gte(date_column, start_date).lte(date_column, end_date).execute())
        return response.data or []
    except Exception as exc:
        log_error(f"Erreur de lecture filtrée par date sur {table_name}", type(exc).__name__)
        return []


def fetch_data_paginated(table_name: str, *, page_size: int = 500,
                         max_rows: int = 10000, order_column: Optional[str] = None) -> list:
    """Lecture paginée explicite ; ne change pas la sémantique des appels existants.

    Une lecture trop volumineuse provoque une erreur, au lieu de tronquer les
    résultats silencieusement. Une colonne de tri stable est indispensable.
    """
    _require_read_permission(table_name)
    if not 1 <= page_size <= 1000 or max_rows < 1:
        raise ValueError("page_size doit être entre 1 et 1000 et max_rows positif")
    valid_cols = _readable_columns(table_name)
    if order_column is None:
        order_column = _PRIMARY_KEY_OVERRIDES.get(table_name, SCHEMA_CONFIG[table_name]["cols"][0])
    if order_column not in valid_cols:
        raise ValueError(f"Colonne de tri inconnue : {order_column}")
    rows: list = []
    # +1 permet de détecter explicitement une troncature au seuil max_rows.
    while len(rows) <= max_rows:
        count = min(page_size, max_rows + 1 - len(rows))
        start = len(rows)
        page = (get_supabase_client().table(table_name)
                .select(_read_projection(table_name))
                .order(order_column).range(start, start + count - 1).execute())
        batch = page.data or []
        rows.extend(batch)
        if len(batch) < count:
            return rows
    raise ValueError(f"Résultat trop volumineux : plus de {max_rows} lignes")


def _signal_sheets_failure(table_name: str, action: str,
                          exc: Exception) -> None:
    """Report an uncertain Sheets backup after Supabase success."""
    _LOG.error(
        "Google Sheets backup unconfirmed: %s %s (%s)",
        action, table_name, type(exc).__name__
    )

    try:
        st.session_state["_erp_sheets_sync_alert"] = (
            f"{action} sur {table_name} confirme dans Supabase, "
            "mais sauvegarde Google Sheets non confirmee. "
            "Ne recommencez pas cette operation. "
            "Verifiez Supabase et Google Sheets avant toute nouvelle tentative."
        )
    except Exception as state_exc:
        _LOG.warning(
            "Session alert unavailable (%s)",
            type(state_exc).__name__
        )

    try:
        log_error(
            "Google Sheets sync failure: " + table_name,
            type(exc).__name__
        )
    except Exception as log_exc:
        _LOG.warning(
            "Google Sheets error log unavailable (%s)",
            type(log_exc).__name__
        )


def _sync_google_sheets_insert(table_name: str, data: dict[str, Any]) -> None:
    if table_name in _NO_SHEETS_SYNC:
        return
    config = SCHEMA_CONFIG[table_name]
    try:
        ligne = [data.get(col, "") for col in config["cols"]]
        append_rows_batch(config["module"], config["sheet"], [ligne], config["cols"])
    except Exception as exc:
        _signal_sheets_failure(table_name, "INSERT", exc)


def _sync_google_sheets_update(table_name: str, id_col: str, target_id: Any,
                               updates: dict[str, Any]) -> None:
    if table_name in _NO_SHEETS_SYNC:
        return
    config = SCHEMA_CONFIG[table_name]
    try:
        update_multiple_cells_by_id(config["module"], config["sheet"], id_col,
                                    target_id, updates)
    except Exception as exc:
        _signal_sheets_failure(table_name, "UPDATE", exc)


def insert_hybrid(table_name: str, data: dict):
    """Creation limitee aux tables autorisees. Supabase reste source de verite.

    Une reponse manquante ou une exception SQL est un resultat INCERTAIN :
    pas de nouvelle operation sans inspection pour eviter les doublons.
    """
    # 010-A-02D-01 : comptes et habilitations exclusivement via RPC auditée.
    if table_name in {"users", "permissions"}:
        raise PermissionError("Mutation de securite interdite par l'API generique")
    if table_name not in _HYBRID_INSERT_TABLES:
        raise PermissionError(f"INSERT direct interdit sur {table_name!r} ; utiliser la RPC metier")
    _check_write_columns(table_name, data)
    if not check_server_permission(table_name):
        log_error("Acces Refuse", f"Tentative d'INSERT bloquee sur {table_name}")
        raise PermissionError(f"Droit d'ecriture refuse pour {table_name!r}")
    try:
        response = get_supabase_client().table(table_name).insert(data).execute()
    except Exception as exc:
        log_error(f"Erreur d'insertion Supabase ({table_name})", type(exc).__name__)
        raise RuntimeError(
            f"INSERT {table_name} non confirme ; verifier Supabase avant de recommencer"
        ) from exc
    result = response.data
    if not isinstance(result, list) or len(result) != 1 or not isinstance(result[0], dict):
        raise RuntimeError(f"INSERT {table_name} non verifiable ; verifier Supabase")
    log_action("INSERT", table_name, _audit_details(table_name, "INSERT", data))
    _sync_google_sheets_insert(table_name, data)
    return result


def update_hybrid(table_name: str, id_col: str, target_id: str, updates: dict):
    """UPDATE limite aux PK et aux colonnes de referentiels sans effet stock."""
    allowed = _HYBRID_UPDATE_FIELDS.get(table_name)
    if allowed is None:
        raise PermissionError(f"UPDATE direct interdit sur {table_name!r} ; utiliser la RPC metier")
    _check_write_columns(table_name, updates)
    if id_col != _HYBRID_UPDATE_PK[table_name]:
        raise ValueError("UPDATE interdit : seul l'identifiant primaire est autorise")
    forbidden = set(updates) - allowed
    if forbidden:
        raise PermissionError(f"UPDATE de colonne protegee interdit : {sorted(forbidden)}")
    if target_id is None or str(target_id).strip() == "":
        raise ValueError("target_id ne peut pas etre vide")
    if not check_server_permission(table_name):
        log_error("Acces Refuse", f"Tentative d'UPDATE bloquee sur {table_name}")
        raise PermissionError(f"Droit d'ecriture refuse pour {table_name!r}")
    try:
        response = (get_supabase_client().table(table_name)
                    .update(updates).eq(id_col, target_id).execute())
    except Exception as exc:
        log_error(f"Erreur de mise a jour Supabase ({table_name})", type(exc).__name__)
        raise RuntimeError(
            f"UPDATE {table_name} non confirme ; verifier Supabase avant de recommencer"
        ) from exc
    result = response.data
    if (not isinstance(result, list) or len(result) != 1
            or not isinstance(result[0], dict)
            or str(result[0].get(id_col)) != str(target_id)):
        raise RuntimeError(f"UPDATE {table_name} non verifiable ; verifier Supabase")
    log_action("UPDATE", table_name,
               _audit_details(table_name, "UPDATE", updates,
                              id_col=id_col, target_id=target_id))
    _sync_google_sheets_update(table_name, id_col, target_id, updates)
    return result
