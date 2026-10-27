"""
Logique métier du module Production.
Gère les Recettes, LignesRecette, les OF (Machine à états & CQ) et la traçabilité des consommations.
Conforme au schéma officiel docs/schema_donnees.md.
"""
import pandas as pd
from core.db_service import (
    check_server_permission, fetch_data, fetch_data_filtered,
)
from core.utils import get_local_now
from modules.stocks.service import _stock_rpc_client
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4
from datetime import date


class FabricationOperationError(RuntimeError):
    """Clôture non confirmée : ne pas relancer avec des paramètres différents."""

    def __init__(self, message: str, *, of_id: str):
        super().__init__(message)
        self.of_id = of_id


def _identifier(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 200:
        raise ValueError(f"{name} invalide (1 à 200 caractères)")
    return value.strip()


def _quantity(value: Any, name: str, *, allow_zero: bool = False) -> str:
    if isinstance(value, bool):
        raise ValueError(f"{name} invalide")
    raw = str(value)
    if len(raw) > 64:
        raise ValueError(f"{name} trop long")
    try:
        n = Decimal(raw)
    except (ValueError, InvalidOperation, TypeError) as exc:
        raise ValueError(f"{name} invalide") from exc
    if (not n.is_finite() or n >= Decimal("1e15")
            or (n < 0 if allow_zero else n <= 0)
            or n.as_tuple().exponent < -12):
        raise ValueError(f"{name} doit être positif et fini")
    return format(n, "f")


def get_recettes() -> pd.DataFrame:
    """Récupère toutes les recettes depuis Supabase."""
    return pd.DataFrame(fetch_data("recettes"))

def get_lignes_recette(recette_id: str = None) -> pd.DataFrame:
    """Récupère les lignes de recette."""
    if recette_id:
        return pd.DataFrame(fetch_data_filtered("lignes_recette", "recette_id", recette_id))
    return pd.DataFrame(fetch_data("lignes_recette"))

def get_ordres_fabrication() -> pd.DataFrame:
    """Récupère tous les ordres de fabrication."""
    return pd.DataFrame(fetch_data("ordres_fabrication"))

def get_consommations_of(of_id: str = None) -> pd.DataFrame:
    """Récupère les consommations de matières par OF."""
    if of_id:
        return pd.DataFrame(fetch_data_filtered("consommations_of", "of_id", of_id))
    return pd.DataFrame(fetch_data("consommations_of"))

def get_controles_qualite(of_id: str = None) -> pd.DataFrame:
    """Récupère le registre des contrôles qualité."""
    if of_id:
        return pd.DataFrame(fetch_data_filtered("controle_qualite", "of_id", of_id))
    return pd.DataFrame(fetch_data("controle_qualite"))

class ProductionCreationError(RuntimeError):
    """La transaction a pu réussir malgré une erreur réseau. Utiliser le même ID."""

    def __init__(self, message: str, *, operation_id: str):
        super().__init__(message)
        self.operation_id = operation_id


def _date_creation(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError(f"{name} doit être au format AAAA-MM-JJ")
    try:
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError()
    except ValueError as exc:
        raise ValueError(f"{name} doit être une date valide AAAA-MM-JJ") from exc
    return value


def _comment(value: Any, name: str, *, max_len: int = 5000) -> str:
    if not isinstance(value, str) or len(value) > max_len:
        raise ValueError(f"{name} invalide")
    return value


def _create_rpc(name: str, params: dict, *, target: str, permissions: tuple[str, ...]) -> str:
    op_id = params["p_operation_id"]
    for table in permissions:
        if check_server_permission(table) is not True:
            raise PermissionError("Droit de création Production refusé")
    try:
        response = _stock_rpc_client().rpc(name, params).execute()
    except Exception as exc:
        raise ProductionCreationError(
            "Création non confirmée : vérifier Supabase avant de reprendre avec le MÊME operation_id",
            operation_id=op_id,
        ) from exc
    result = response.data
    if (not isinstance(result, dict)
            or result.get("operation_id") != op_id
            or not isinstance(result.get(target), str)
            or not result[target].strip()):
        raise ProductionCreationError(
            "Réponse SQL non vérifiable : vérifier Supabase avec cet operation_id",
            operation_id=op_id,
        )
    return result[target]


def create_recette(pf_id: str, version: str, rendement_unite: float,
                   instructions: str, panier_lignes: list,
                   *, operation_id: str | None = None,
                   date_effet: str | None = None) -> str:
    """Crée la recette ET toutes ses lignes dans la même transaction PostgreSQL."""
    pf = _identifier(pf_id, "Produit fini")
    ver = _identifier(version, "Version recette")
    yield_qty = _quantity(rendement_unite, "Rendement")
    info = _comment(instructions, "Instructions")
    if not isinstance(panier_lignes, list) or not 1 <= len(panier_lignes) <= 200:
        raise ValueError("Recette : entre 1 et 200 composants nécessaires")
    seen = set()
    lines = []
    for item in panier_lignes:
        if not isinstance(item, dict):
            raise ValueError("Ligne de recette invalide")
        mp = _identifier(item.get("mp_id"), "Matière première")
        if mp in seen:
            raise ValueError("Matière première en double dans la recette")
        seen.add(mp)
        qty = _quantity(item.get("quantite_par_unite"), "Quantité matière")
        if Decimal(qty) < Decimal("0.000000000001"):
            raise ValueError("Précision insuffisante pour la quantité matière")
        lines.append({"mp_id": mp, "quantite_par_unite": qty})
    op_id = (_identifier(operation_id, "Identifiant d'opération")
             if operation_id is not None else f"PREC-{uuid4()}")
    if len(op_id) > 128:
        raise ValueError("Identifiant d'opération trop long")
    return _create_rpc("erp_create_recipe", {
        "p_operation_id": op_id, "p_pf_id": pf, "p_version": ver,
        "p_rendement_unite": yield_qty, "p_instructions": info,
        "p_date_effet": _date_creation(
            date_effet if date_effet is not None else get_local_now().strftime("%Y-%m-%d"),
            "Date d'effet"),
        "p_lignes": lines,
    }, target="recette_id", permissions=("recettes", "lignes_recette"))


def create_ordre_fabrication(pf_id: str, recette_id: str, sku_id: str,
                              quantite_prevue: float, date_planification: str,
                              notes: str, *, operation_id: str | None = None) -> str:
    """Crée un OF planifié avec attribution atomique du numéro OF en base."""
    pf = _identifier(pf_id, "Produit fini")
    recipe = _identifier(recette_id, "Recette")
    sku = _identifier(sku_id, "SKU")
    qty = _quantity(quantite_prevue, "Quantité prévue")
    if Decimal(qty) != Decimal(qty).to_integral_value():
        raise ValueError("Quantité prévue : nombre entier de SKU requis")
    date_value = _date_creation(date_planification, "Date planifiée")
    comment = _comment(notes, "Notes")
    op_id = (_identifier(operation_id, "Identifiant d'opération")
             if operation_id is not None else f"POF-{uuid4()}")
    if len(op_id) > 128:
        raise ValueError("Identifiant d'opération trop long")
    return _create_rpc("erp_create_manufacturing_order", {
        "p_operation_id": op_id, "p_pf_id": pf, "p_recette_id": recipe,
        "p_sku_id": sku, "p_quantite_prevue": qty,
        "p_date_planification": date_value, "p_notes": comment,
    }, target="of_id", permissions=("ordres_fabrication",))

def changer_statut_of(of_id: str, nouveau_statut: str):
    """Démarre un OF sans permettre de rouvrir un OF terminé/rejeté.

    La seule transition autorisée ici est PLANIFIE -> EN_COURS. La RPC
    PostgreSQL verrouille l'OF et vérifie son statut réel. Toutes les
    clôtures TERMINE/REJETE passent par ``enregistrer_controle_qualite``.
    """
    of_id = _identifier(of_id, "Identifiant OF")
    if nouveau_statut != "EN_COURS":
        raise ValueError("Seul le démarrage EN_COURS est autorisé par cette fonction")
    if check_server_permission("ordres_fabrication") is not True:
        raise PermissionError("Droit de Production refusé")
    try:
        response = _stock_rpc_client().rpc("erp_start_manufacturing_order", {
            "p_of_id": of_id,
        }).execute()
    except Exception as exc:
        raise FabricationOperationError(
            "Démarrage non confirmé : consulter l'OF en base avant de recommencer",
            of_id=of_id,
        ) from exc
    if not isinstance(response.data, dict) or response.data.get("of_id") != of_id \
            or response.data.get("statut") != "EN_COURS":
        raise FabricationOperationError("Démarrage non vérifiable", of_id=of_id)
    return response.data


def enregistrer_controle_qualite(
    of_id: str,
    conforme: str,
    remarques: str,
    controleur: str,
    quantite_produite: float = 0.0,
    emballage_mp_id: str = None,
    emballage_consomme: float = 0.0,
):
    """Clôture atomique d'un OF : CQ + FIFO réel + entrée PF + statut.

    Ne fait JAMAIS plusieurs écritures indépendantes depuis Python. La RPC
    erp_close_manufacturing_order s'exécute en une transaction PostgreSQL,
    dont le contenu est contrôlé côté base. Rejouer les MÊMES paramètres
    (même OF) après un timeout : aucune nouvelle consommation n'est créée.

    Les recettes actuelles utilisent ``quantite_par_unite`` : quantité MP par
    unité produite. Aucun facteur de batch n'est inventé ici.

    IMPORTANT : nécessite sql/003_atomic_manufacturing_close.sql sur une
    instance Supabase de TEST et la clé serveur du module Stocks.
    """
    of_id = _identifier(of_id, "Identifiant OF")
    if conforme not in ("OUI", "NON"):
        raise ValueError("Conformité attendue : OUI ou NON")
    if not isinstance(remarques, str) or len(remarques) > 5000:
        raise ValueError("Remarques invalides (max 5000 caractères)")
    controleur = _identifier(controleur, "Contrôleur")
    quantity = _quantity(quantite_produite, "Quantité produite", allow_zero=conforme == "NON")
    packaging_qty = _quantity(emballage_consomme, "Quantité d'emballage", allow_zero=True)
    has_packaging = emballage_mp_id is not None and bool(str(emballage_mp_id).strip())
    packaging_id = _identifier(emballage_mp_id, "Emballage MP") if has_packaging else None
    if (packaging_id is None) != (Decimal(packaging_qty) == 0):
        raise ValueError("Emballage et quantité doivent être renseignés ensemble")
    if conforme == "NON" and (Decimal(quantity) != 0 or packaging_id is not None):
        raise ValueError("Un OF rejeté ne peut pas entrer de PF ni consommer de matières")

    # Même règle métier que les autres services : le compte ET le rôle sont
    # vérifiés par Supabase, sans se fier au rôle du navigateur.
    if check_server_permission("controle_qualite") is not True:
        raise PermissionError("Droit de Production refusé")
    if conforme == "OUI":
        if (check_server_permission("mouvements") is not True
                or check_server_permission("mouvements_pf") is not True):
            raise PermissionError("Droits Stocks nécessaires à la clôture d'OF")

    params = {
        "p_of_id": of_id,
        "p_conforme": conforme,
        "p_remarques": remarques,
        "p_controleur": controleur,
        "p_quantite_produite": quantity,
        "p_emballage_mp_id": packaging_id,
        "p_emballage_consomme": packaging_qty,
    }
    try:
        response = _stock_rpc_client().rpc("erp_close_manufacturing_order", params).execute()
    except Exception as exc:
        # Ne pas refaire plusieurs mouvements séparément après un timeout !
        raise FabricationOperationError(
            "Clôture non confirmée : consulter l'OF en base, puis réessayer "
            "avec les MÊMES paramètres", of_id=of_id,
        ) from exc
    result = response.data
    if not isinstance(result, dict) or result.get("of_id") != of_id or result.get("statut") not in ("TERMINE", "REJETE"):
        raise FabricationOperationError(
            "Réponse de clôture non vérifiable : contrôler l'OF en base", of_id=of_id,
        )
    if result["statut"] != ("TERMINE" if conforme == "OUI" else "REJETE"):
        raise FabricationOperationError("Statut inattendu : contrôler l'OF en base", of_id=of_id)
    return result

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