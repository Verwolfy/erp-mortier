"""Écran Ventes : lecture autorisée, transactions idempotentes et expédition par commande.

Tous les appels DRAFT/VALIDATE/CANCEL/SHIP sont réalisés par le service Ventes.
Un échec réseau laisse l'opération figée en session : une reprise utilise le
même operation_id et le même contenu, même après un rerun Streamlit.
"""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
import logging
from uuid import uuid4

import pandas as pd
import streamlit as st

from config.roles import has_permission
from core.db_service import fetch_data_paginated, get_supabase_client
from modules.ventes.service import (
    annuler_facture,
    calculer_montants_facture,
    create_facture_brouillon,
    creer_bon_livraison,
    creer_commande_client,
    get_factures,
    get_lignes_facture,
    valider_facture,
)

_LOG = logging.getLogger(__name__)
# Repère public de la livraison de l'écran, sans revendication d'un SHA
# déployé. Permet une vérification visuelle de Streamlit après mise à jour.
_UI_REVISION = "SOF-ERP-20261029-TVA-ASOF-01"
_ACTIVE = frozenset({"oui", "true", "1", "actif", "active", "yes"})
_ACTIONS = frozenset({"draft", "validate", "cancel", "ship", "order"})
_REQUIRED = {
    "draft": frozenset({"client_id", "date_echeance", "panier", "remise_globale",
                         "paiement_especes", "is_avoir", "facture_origine_id"}),
    "validate": frozenset({"facture_id"}),
    "cancel": frozenset({"facture_id"}),
    "ship": frozenset({"commande_vente_id", "transporteur", "zone", "items_livraison"}),
    "order": frozenset({"client_id", "date_commande", "lignes"}),
}
_LIMIT = Decimal("1e15")
_EXPEDIABLE_STATES = frozenset({"EN_ATTENTE", "CONFIRMEE", "VALIDEE", "EN_COURS", "PARTIELLEMENT_LIVREE"})


def _mark_ventes_activity() -> None:
    """Signale une interaction sans renouvellement direct."""
    st.session_state["_erp_ventes_interacted"] = True


def _sale_access() -> tuple[str, bool] | None:
    """Contrôle actualisé depuis Supabase, y compris pour les lectures."""
    try:
        if st.session_state.get("authenticated") is not True:
            return None
        session_user = st.session_state.get("user")
        if not isinstance(session_user, dict):
            return None
        user_id = session_user.get("user_id")
        if not isinstance(user_id, str) or not user_id.strip():
            return None
        result = (get_supabase_client().table("users")
                  .select("user_id,role,actif").eq("user_id", user_id)
                  .limit(1).execute())
        records = result.data or []
        if len(records) != 1 or not isinstance(records[0], dict):
            return None
        user = records[0]
        if user.get("user_id") != user_id:
            return None
        active = user.get("actif")
        if active is not True and str(active).strip().casefold() not in _ACTIVE:
            return None
        role = user.get("role")
        if not isinstance(role, str) or not role.strip():
            return None
        if has_permission(role, "Ventes", "lecture") is not True:
            return None
        return user_id, has_permission(role, "Ventes", "ecriture") is True
    except Exception as exc:
        _LOG.warning("Lecture Ventes refusée : autorisation non vérifiable (%s)", type(exc).__name__)
        return None


def _decimal(value: object, label: str, *, positive: bool = False) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{label} invalide")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{label} invalide") from exc
    if not number.is_finite() or number >= _LIMIT or number < 0 or (positive and number <= 0):
        raise ValueError(f"{label} invalide")
    return number


def _cart_key(user_id: str) -> str:
    return f"ventes_panier_{user_id}"


def _operation_key(kind: str, user_id: str) -> str:
    if kind not in _ACTIONS:
        raise ValueError("Action Ventes inconnue")
    return f"ventes_{kind}_{user_id}"


def _execute_operation(kind: str, user_id: str) -> None:
    """Ne crée JAMAIS un nouvel identifiant après un échec réseau."""
    key = _operation_key(kind, user_id)
    record = st.session_state[key]
    if record["status"] == "confirmed":
        return
    try:
        payload = deepcopy(record["payload"])
        operation_id = record["operation_id"]
        if kind == "draft":
            result = create_facture_brouillon(**payload, operation_id=operation_id)
            if not isinstance(result, str) or not result.strip():
                raise RuntimeError("Numéro de facture non confirmé")
            document_id = result
        elif kind == "validate":
            result = valider_facture(**payload, operation_id=operation_id)
            if not isinstance(result, dict) or result.get("statut") != "VALIDE" \
                    or result.get("facture_id") != payload["facture_id"]:
                raise RuntimeError("Validation non confirmée")
            document_id = payload["facture_id"]
        elif kind == "cancel":
            result = annuler_facture(**payload, operation_id=operation_id)
            if not isinstance(result, dict) or result.get("statut") != "ANNULE" \
                    or result.get("facture_id") != payload["facture_id"]:
                raise RuntimeError("Annulation non confirmée")
            document_id = payload["facture_id"]
        elif kind == "order":
            result = creer_commande_client(**payload, operation_id=operation_id)
            if not isinstance(result, str) or not result.strip():
                raise RuntimeError("Sales order not confirmed")
            document_id = result
        elif kind == "ship":
            result = creer_bon_livraison(**payload, operation_id=operation_id)
            if not isinstance(result, str) or not result.strip():
                raise RuntimeError("BL non confirmé")
            document_id = result
    except (ValueError, PermissionError) as exc:
        # Le service valide les paramètres et droits avant le RPC.
        _LOG.warning("Opération Ventes refusée localement (%s)", type(exc).__name__)
        del st.session_state[key]
        st.error("Opération refusée : corrigez les données ou les autorisations.")
        return
    except Exception as exc:
        # Échec incertain après éventuel COMMIT : l'opération reste verrouillée.
        _LOG.warning("Opération Ventes non confirmée (%s)", type(exc).__name__)
        record["status"] = "uncertain"
        st.error("Opération non confirmée. Vérifiez-la dans Supabase avant de réessayer.")
        st.code(record["operation_id"])
        return
    record["status"] = "confirmed"
    record["document_id"] = document_id
    if kind == "draft":
        st.session_state[_cart_key(user_id)] = []
    elif kind == "order":
        st.session_state[f"order_cart_{user_id}"] = []
    st.rerun()


def _start_operation(kind: str, user_id: str, payload: dict) -> None:
    key = _operation_key(kind, user_id)
    if key in st.session_state:
        st.error("Une opération est déjà en attente : utilisez son dossier de reprise.")
        return
    st.session_state[key] = {
        "status": "uncertain",
        "operation_id": f"SALE-UI-{uuid4().hex}",
        "payload": deepcopy(payload),
    }
    _execute_operation(kind, user_id)


def _operation_panel(kind: str, user_id: str) -> bool:
    key = _operation_key(kind, user_id)
    if key not in st.session_state:
        return False
    record = st.session_state[key]
    valid = (isinstance(record, dict) and record.get("status") in {"uncertain", "confirmed"}
             and isinstance(record.get("operation_id"), str)
             and record["operation_id"].startswith("SALE-UI-")
             and isinstance(record.get("payload"), dict)
             and _REQUIRED[kind].issubset(record["payload"])
             and (record["status"] != "confirmed" or
                  (isinstance(record.get("document_id"), str) and bool(record["document_id"]))))
    if not valid:
        st.error("Dossier Ventes illisible : demander une vérification à l'administrateur.")
        return True
    st.code(record["operation_id"])
    if record["status"] == "uncertain":
        st.warning("Opération en attente de confirmation : ne modifiez pas les quantités.")
        st.info("Après vérification de la base, la reprise réutilise le même contenu et le même identifiant.")
        if st.button("Réessayer exactement la même opération", key=f"retry_{kind}_{user_id}", on_click=_mark_ventes_activity):
            _execute_operation(kind, user_id)
    else:
        st.success(f"Document {record['document_id']} confirmé.")
        if st.button("Préparer une nouvelle opération", key=f"new_{kind}_{user_id}", on_click=_mark_ventes_activity):
            del st.session_state[key]
            st.rerun()
    return True


def _read_required(table: str) -> pd.DataFrame:
    """Lecture complète ou échec explicite : pas de calcul sur données tronquées."""
    return pd.DataFrame(fetch_data_paginated(table, max_rows=10000))


def _valid_origins(factures: pd.DataFrame, client_id: str) -> list[str]:
    if factures.empty:
        return []
    required = {"client_id", "type_facture", "statut", "facture_id"}
    if not required.issubset(factures.columns):
        raise ValueError("Colonnes Factures manquantes")
    rows = factures[(factures["client_id"] == client_id)
                    & (factures["type_facture"] == "FactureClient")
                    & (factures["statut"] == "VALIDE")]
    return rows["facture_id"].tolist()


def _remaining_for_order(order_id: str, order_lines: pd.DataFrame,
                         shipments: pd.DataFrame, shipment_lines: pd.DataFrame) -> dict[str, Decimal]:
    """Agrège les quantités déjà EXPÉDIÉES, y compris les BL partiels et multi-lots."""
    if not isinstance(order_id, str) or not order_id.strip():
        raise ValueError("Commande client absente")
    if order_lines.empty or not {"commande_vente_id", "sku_id", "quantite"}.issubset(order_lines.columns):
        raise ValueError("Aucune ligne de commande exploitable")
    selected = order_lines[order_lines["commande_vente_id"] == order_id]
    if selected.empty:
        raise ValueError("Commande client sans lignes")
    ordered = {}
    for row in selected.to_dict("records"):
        sku = str(row["sku_id"] or "").strip()
        if not sku:
            raise ValueError("SKU de commande absent")
        ordered[sku] = ordered.get(sku, Decimal(0)) + _decimal(row["quantite"], "Quantité commandée", positive=True)
    if shipments.empty:
        return ordered
    if not {"bl_id", "commande_vente_id", "statut"}.issubset(shipments.columns):
        raise ValueError("Colonnes BL manquantes")
    shipped_bls = set(shipments.loc[(shipments["commande_vente_id"] == order_id)
                                        & (shipments["statut"] == "EXPEDIE"), "bl_id"])
    if not shipped_bls:
        return ordered
    if shipment_lines.empty or not {"bl_id", "sku_id", "quantite_livree"}.issubset(shipment_lines.columns):
        raise ValueError("Lignes de BL introuvables")
    shipped = {}
    for row in shipment_lines[shipment_lines["bl_id"].isin(shipped_bls)].to_dict("records"):
        sku = str(row["sku_id"] or "").strip()
        shipped[sku] = shipped.get(sku, Decimal(0)) + _decimal(row["quantite_livree"], "Quantité livrée", positive=True)
    if set(shipped) - set(ordered):
        raise ValueError("Livraison historique incohérente avec la commande")
    remaining = {sku: qty - shipped.get(sku, Decimal(0)) for sku, qty in ordered.items()}
    if any(qty < 0 for qty in remaining.values()):
        raise ValueError("Commande historiquement sur-livrée : vérification requise")
    return remaining


def _draft_tab(user_id: str, can_write: bool, factures: pd.DataFrame) -> None:
    st.subheader("Créer une facture ou un avoir (brouillon)")
    st.warning(
        "Attention : le calcul historique des brouillons utilise encore une TVA "
        "uniforme et un éventuel timbre sur facture. La classification fiscale "
        "par SKU ne pilote pas encore la transaction SQL. Cette fonction ne "
        "constitue pas une facturation réglementaire homologuée."
    )
    if not can_write:
        st.info("Mode lecture seule")
        return
    if _operation_panel("draft", user_id):
        return
    clients = _read_required("clients")
    skus = _read_required("sku_conditionnement")
    products = _read_required("produits")
    if clients.empty or skus.empty or products.empty:
        st.warning("Référentiels client / produits / SKU manquants.")
        return
    clients = clients[clients["actif"] == "OUI"] if "actif" in clients.columns else clients
    skus = skus[skus["actif"] == "OUI"] if "actif" in skus.columns else skus
    products = products[products["actif"] == "OUI"] if "actif" in products.columns else products
    if clients.empty or skus.empty or products.empty:
        st.warning("Aucun client ou produit actif.")
        return
    client_labels = {r["client_id"]: f"{r['client_id']} - {r['nom']}" for _, r in clients.iterrows()}
    client_id = st.selectbox("Client", list(client_labels), format_func=lambda x: client_labels[x], key="vente_client", on_change=_mark_ventes_activity)
    echeance = st.date_input("Date d'échéance", key="vente_echeance")
    type_doc = st.selectbox("Type de document", ["FactureClient", "FactureAvoir"], key="vente_type", on_change=_mark_ventes_activity)
    is_avoir = type_doc == "FactureAvoir"
    origine = ""
    if is_avoir:
        choices = _valid_origins(factures, client_id)
        if not choices:
            st.warning("Aucune facture client validée pour cet avoir.")
            return
        origine = st.selectbox("Facture d'origine", choices, key="vente_origine", on_change=_mark_ventes_activity)
    names = {r["pf_id"]: str(r["nom"]) for _, r in products.iterrows()}
    labels = {r["sku_id"]: f"{names.get(r['pf_id'], 'Produit')} - {r.get('format','')} ({r['sku_id']})"
              for _, r in skus.iterrows()}
    if not labels:
        st.warning("Aucun SKU disponible.")
        return
    cart_key = _cart_key(user_id)
    context_key = f"ventes_panier_contexte_{user_id}"
    current_context = (client_id, type_doc, origine)
    previous_context = st.session_state.get(context_key)
    if previous_context is not None and previous_context != current_context:
        st.session_state[cart_key] = []
        st.warning("Client, type de document ou origine modifié : panier vidé pour éviter une erreur de facturation.")
    st.session_state[context_key] = current_context
    cart = st.session_state.setdefault(cart_key, [])
    if not isinstance(cart, list):
        st.error("Panier non exploitable.")
        return
    sku_id = st.selectbox("Produit", list(labels), format_func=lambda x: labels[x], key="vente_sku", on_change=_mark_ventes_activity)
    product_row = skus[skus["sku_id"] == sku_id].iloc[0]
    prix = _decimal(product_row.get("prix_vente_defaut", 0) or 0, "Prix par défaut")
    qte = st.number_input("Quantité (unités SKU entières)", min_value=1, value=1, step=1, key="vente_qte")
    pu = st.number_input("Prix unitaire HT (DZD)", min_value=0.0, value=float(prix), step=1.0, key="vente_pu")
    rem_type = st.selectbox("Remise", ["Montant (DZD)", "Pourcentage (%)"], key="vente_rem_type", on_change=_mark_ventes_activity)
    remise_value = st.number_input("Valeur de remise", min_value=0.0, step=1.0, key="vente_rem_val")
    if st.button("Ajouter au panier", key="vente_add", on_click=_mark_ventes_activity):
        quant = _decimal(qte, "Quantité", positive=True)
        if quant != quant.to_integral_value():
            st.error("Le nombre de conditionnements doit être entier.")
            return
        prix_u = _decimal(pu, "Prix unitaire")
        discount = _decimal(remise_value, "Remise")
        gross = quant * prix_u
        if rem_type == "Pourcentage (%)":
            if discount > 100:
                st.error("Remise supérieure à 100 %.")
                return
            discount = gross * discount / Decimal(100)
        if discount > gross:
            st.error("Remise supérieure au montant de ligne.")
            return
        cart.append({"sku_id": sku_id, "nom_produit": labels[sku_id], "quantite": float(quant),
                     "prix_unitaire": float(prix_u), "remise": float(discount)})
        st.rerun()
    if not cart:
        st.info("Panier vide.")
        return
    st.dataframe(pd.DataFrame(cart), hide_index=True, use_container_width=True)
    if st.button("Vider le panier", key="vente_empty", on_click=_mark_ventes_activity):
        st.session_state[cart_key] = []
        st.rerun()
    global_discount = st.number_input("Remise globale (DZD)", min_value=0.0, step=1.0)
    cash = st.checkbox("Paiement en espèces (timbre fiscal)", disabled=is_avoir)
    try:
        totals = calculer_montants_facture(cart, global_discount, bool(cash) if not is_avoir else False)
    except ValueError as exc:
        st.error(str(exc))
        return
    st.info(f"Net HT : {totals['net_a_payer']:,.2f} DZD | TVA : {totals['total_tva']:,.2f} DZD | TTC : {totals['total_ttc']:,.2f} DZD")
    st.caption("Les taux de TVA/timbre sont ceux du service actuel, à valider par la comptabilité.")
    if st.button("Enregistrer le brouillon", key="vente_draft_submit", type="primary", on_click=_mark_ventes_activity):
        _start_operation("draft", user_id, {
            "client_id": client_id, "date_echeance": str(echeance), "panier": deepcopy(cart),
            "remise_globale": global_discount, "paiement_especes": bool(cash) if not is_avoir else False,
            "is_avoir": is_avoir, "facture_origine_id": origine,
        })
    st.caption("PDF désactivé : les coordonnées légales de l'entreprise doivent provenir de paramètres vérifiés, pas de valeurs fictives.")


def _order_tab(user_id: str, can_write: bool) -> None:
    st.subheader("Commandes clients")
    st.caption("Commande et livraison distinctes de la facturation : aucun nouveau document facture n'est cr\u00e9\u00e9.")
    # Ne jamais autoriser une seconde tentative avec de nouvelles donn\u00e9es avant confirmation.
    if _operation_panel("order", user_id):
        return
    orders = _read_required("commandes_ventes")
    if not orders.empty:
        needed = {"commande_vente_id", "client_id", "statut"}
        if not needed.issubset(orders.columns):
            st.error("Colonnes Commandes clients manquantes")
            return
        st.dataframe(orders[["commande_vente_id", "client_id", "statut"]],
                     use_container_width=True, hide_index=True)
    if not can_write:
        st.info("Mode lecture seule")
        return
    clients = _read_required("clients")
    skus = _read_required("sku_conditionnement")
    if clients.empty or skus.empty:
        st.warning("Aucun client ou SKU disponible")
        return
    if not {"client_id", "nom", "actif"}.issubset(clients.columns) or not \
            {"sku_id", "actif", "prix_vente_defaut"}.issubset(skus.columns):
        st.error("R\u00e9f\u00e9rentiel clients ou SKU incomplet")
        return
    clients = clients[clients["actif"].astype(str).str.strip().str.upper() == "OUI"]
    skus = skus[skus["actif"].astype(str).str.strip().str.upper() == "OUI"]
    skus = skus[skus["sku_id"] != "SKU-007"]  # Validation physique en attente.
    if clients.empty or skus.empty:
        st.warning("Aucun client ou SKU actif et autoris\u00e9")
        return
    client_labels = {r["client_id"]: f'{r["client_id"]} - {r["nom"]}'
                     for _, r in clients.iterrows()}
    sku_labels = {r["sku_id"]: str(r["sku_id"]) for _, r in skus.iterrows()}
    client_id = st.selectbox("Client", list(client_labels),
                             format_func=lambda x: client_labels[x],
                             key=f"order_client_{user_id}", on_change=_mark_ventes_activity)
    order_date = st.date_input("Date de commande", key=f"order_date_{user_id}")
    cart_key = f"order_cart_{user_id}"
    owner_key = f"order_cart_client_{user_id}"
    if st.session_state.get(owner_key) != client_id:
        if st.session_state.get(cart_key):
            st.info("Changement de client : panier pr\u00e9c\u00e9dent effac\u00e9.")
        st.session_state[cart_key] = []
        st.session_state[owner_key] = client_id
    cart = st.session_state[cart_key]
    sku_id = st.selectbox("Produit SKU", list(sku_labels),
                          format_func=lambda x: sku_labels[x],
                          key=f"order_sku_{user_id}", on_change=_mark_ventes_activity)
    price_raw = skus.loc[skus["sku_id"] == sku_id, "prix_vente_defaut"].iloc[0]
    try:
        default_price = float(_decimal(price_raw, "Prix unitaire"))
    except (ValueError, TypeError, OverflowError):
        default_price = 0.0
    with st.form(f"order_add_line_{user_id}"):
        qty = st.number_input("Quantit\u00e9 (unit\u00e9s SKU)", min_value=1, value=1, step=1)
        price = st.number_input("Prix unitaire HT (DZD)", min_value=0.0,
                                value=default_price, step=0.01, format="%.2f",
                                key=f"order_price_{user_id}_{sku_id}")
        add = st.form_submit_button("Ajouter au panier", on_click=_mark_ventes_activity)
    if add:
        try:
            amount = _decimal(qty, "Quantit\u00e9", positive=True)
            unit_price = _decimal(price, "Prix unitaire")
            if amount != amount.to_integral_value() or unit_price.as_tuple().exponent < -2:
                raise ValueError("Quantit\u00e9 ou prix invalide")
            if len(cart) >= 500 or any(x["sku_id"] == sku_id for x in cart):
                raise ValueError("SKU d\u00e9j\u00e0 pr\u00e9sent ou limite de lignes atteinte")
            cart.append({"sku_id": sku_id, "quantite": int(amount),
                         "prix_unitaire": format(unit_price, ".2f")})
        except (ValueError, TypeError, OverflowError) as exc:
            st.error(str(exc))
    if not cart:
        st.info("Ajoutez au moins une ligne avant d'enregistrer la commande.")
        return
    st.dataframe(pd.DataFrame(cart), use_container_width=True, hide_index=True)
    if st.button("Vider le panier", key=f"order_clear_{user_id}", on_click=_mark_ventes_activity):
        st.session_state[cart_key] = []
        st.rerun()
    if st.button("Enregistrer la commande", key=f"order_save_{user_id}", type="primary", on_click=_mark_ventes_activity):
        _start_operation("order", user_id, {
            "client_id": client_id, "date_commande": str(order_date),
            "lignes": deepcopy(cart),
        })


def _ship_tab(user_id: str, can_write: bool) -> None:
    st.subheader("Expédition / Bons de livraison")
    st.info("Un BL est rattaché à une vraie commande client, jamais à un numéro de facture.")
    if not can_write:
        st.info("Mode lecture seule")
        return
    if _operation_panel("ship", user_id):
        return
    orders = _read_required("commandes_ventes")
    if orders.empty:
        st.warning("Aucune commande client disponible : impossible d'expédier à partir d'une facture seule.")
        return
    if not {"commande_vente_id", "statut"}.issubset(orders.columns):
        st.error("Schéma des commandes incomplet.")
        return
    orders = orders[orders["statut"].isin(_EXPEDIABLE_STATES)]
    if orders.empty:
        st.info("Aucune commande client expédiable.")
        return
    order_labels = {r["commande_vente_id"]: f"{r['commande_vente_id']} ({r.get('statut','')})"
                    for _, r in orders.iterrows()}
    order_id = st.selectbox("Commande client", list(order_labels), format_func=lambda x: order_labels[x], on_change=_mark_ventes_activity)
    order_lines = _read_required("lignes_commande_ventes")
    shipments = _read_required("bons_livraison")
    shipment_lines = _read_required("lignes_bons_livraison")
    try:
        remaining = _remaining_for_order(order_id, order_lines, shipments, shipment_lines)
    except ValueError as exc:
        st.error(f"Expédition bloquée : {exc}")
        return
    remaining = {sku: qty for sku, qty in remaining.items() if qty > 0}
    if not remaining:
        st.info("Commande intégralement livrée.")
        return
    stock_pf = _read_required("stock_actuel_pf")
    stock_map = {r["sku_id"]: _decimal(r["quantite_disponible"], "Stock PF")
                 for _, r in stock_pf.iterrows()} if not stock_pf.empty else {}
    items = []
    with st.form(f"vente_ship_{order_id}"):
        transporteur = st.text_input("Transporteur", value="Transport Interne")
        zone = st.text_input("Zone de livraison")
        for i, (sku, to_deliver) in enumerate(remaining.items()):
            if to_deliver != to_deliver.to_integral_value():
                st.error(f"Quantité de commande fractionnaire pour {sku} : corriger la commande avant expédition.")
                return
            stock = stock_map.get(sku, Decimal(0))
            if stock < 0:
                st.error("Stock PF incohérent.")
                return
            maximum = min(stock, to_deliver)
            st.write(f"{sku} : reste {to_deliver} | stock PF {stock}")
            amount = st.number_input(f"Quantité à livrer — {sku}", min_value=0,
                                     max_value=int(maximum), value=0, step=1,
                                     key=f"ship_{order_id}_{sku}_{i}")
            if amount > 0:
                items.append({"sku_id": sku, "quantite_livree": float(_decimal(amount, "Livraison", positive=True))})
        if st.form_submit_button("Valider le BL et sortir le stock PF", type="primary", on_click=_mark_ventes_activity):
            if not items:
                st.error("Sélectionnez au moins une quantité à livrer.")
            else:
                _start_operation("ship", user_id, {
                    "commande_vente_id": order_id, "transporteur": transporteur,
                    "zone": zone, "items_livraison": items,
                })
    st.caption("Aucun lot saisi manuellement : le SQL attribue les lots réellement prélevés en FIFO.")


def _workflow_tab(user_id: str, can_write: bool, factures: pd.DataFrame) -> None:
    st.subheader("Factures et workflow")
    if factures.empty:
        st.info("Aucune facture")
        return
    st.dataframe(factures, use_container_width=True, hide_index=True)
    if not can_write:
        return
    if _operation_panel("validate", user_id) or _operation_panel("cancel", user_id):
        return
    if not {"facture_id", "statut"}.issubset(factures.columns):
        st.error("Colonnes Factures manquantes")
        return
    eligible = factures[factures["statut"] == "BROUILLON"]
    if eligible.empty:
        st.info("Aucun brouillon pouvant être validé ou annulé.")
        return
    labels = eligible["facture_id"].tolist()
    invoice_id = st.selectbox("Brouillon à traiter", labels, on_change=_mark_ventes_activity)
    st.info("Validation et annulation n'entraînent aucun mouvement de stock.")
    if st.button("Valider la facture", key="vente_validate", on_click=_mark_ventes_activity):
        _start_operation("validate", user_id, {"facture_id": invoice_id})
    if st.button("Annuler ce brouillon", key="vente_cancel", on_click=_mark_ventes_activity):
        _start_operation("cancel", user_id, {"facture_id": invoice_id})
    st.caption("Une facture VALIDÉE n'est pas annulable ici : un avoir doit suivre le processus financier adapté.")


def show_ventes_page() -> None:
    st.title("Ventes & Facturation")
    access = _sale_access()
    if access is None:
        st.error("Accès Ventes refusé : session ou droit de lecture non confirmé.")
        return
    user_id, can_write = access
    st.caption(f"Version interface Ventes : {_UI_REVISION}")
    # Ces lectures doivent intervenir APRES validation fraîche de l'identité.
    try:
        invoices = get_factures()
        tab_draft, tab_order, tab_ship, tab_workflow, tab_tva = st.tabs([
            "Facture / Avoir", "Commandes clients", "Bons de livraison",
            "Suivi factures", "TVA par SKU (contrôle)",
        ])
        with tab_draft:
            _draft_tab(user_id, can_write, invoices)
        with tab_order:
            _order_tab(user_id, can_write)
        with tab_ship:
            _ship_tab(user_id, can_write)
        with tab_workflow:
            _workflow_tab(user_id, can_write, invoices)
        with tab_tva:
            _controle_tva_sku_tab(user_id)
    except Exception as exc:
        _LOG.warning("Interface Ventes interrompue (%s)", type(exc).__name__)
        st.error("Consultation Ventes interrompue : vérifier la connexion et la cohérence des données.")


def _controle_tva_sku_tab(user_id: str) -> None:
    """Photographie des dossiers TVA SKU ; aucun taux injecté en facture."""
    st.subheader("État de qualification fiscale TVA par SKU")
    st.caption(
        "Règle métier ventes : TVA normale de 19 % (paramètre réglementaire), "
        "ou exonération client à 0 % uniquement sur attestation validée et "
        "couvrant les articles facturés. Aucun taux réduit à 9 % pour ce business. "
        "Cette vue n'active pas le calcul transactionnel."
    )
    if not st.button("Contrôler la couverture fiscale", key="ventes_tva_coverage"):
        return
    _mark_ventes_activity()
    access = _sale_access()  # relire la session et le rôle serveur au clic
    if access is None or access[0] != user_id:
        st.error("Lecture TVA refusée : autorisation non vérifiable.")
        return
    from core.utils import get_local_now
    from core.couverture_tva_sku import (
        QualificationTVAIndisponible, verifier_couverture_tva,
    )
    try:
        skus = fetch_data_paginated("sku_conditionnement")
        response = (
            get_supabase_client().table("erp_sku_fiscalite")
            .select("sku_id,date_effet,date_fin,categorie_tva,code_parametre,"
                    "statut,source_juridique,justification,date_verification,"
                    "valide_par,date_validation", count="exact")
            .range(0, 999).execute()
        )
        rows = response.data
        if (not isinstance(rows, list) or isinstance(response.count, bool)
                or not isinstance(response.count, int)
                or response.count != len(rows) or len(rows) > 1000):
            raise QualificationTVAIndisponible("Lecture TVA incomplète")
        result = verifier_couverture_tva(
            skus, rows, get_local_now().date().isoformat(), uniquement_actifs=True
        )
    except Exception as exc:
        _LOG.warning("Couverture TVA non consultable (%s)", type(exc).__name__)
        st.error("Référentiel TVA incomplet ou inaccessible ; aucune conclusion possible.")
        return
    st.metric("SKU contrôlés", result["nombre_skus"])
    for key, label in (
        ("NON_CLASSE", "SKU non classés"),
        ("A_VALIDER", "Dossiers à valider"),
        ("VALIDE", "Dossiers validés"),
    ):
        st.metric(label, result["par_statut"][key])
    if result["lignes"]:
        st.dataframe(
            pd.DataFrame(result["lignes"]), use_container_width=True,
            hide_index=True,
        )
    # Export strictement local et après revalidation des droits de lecture.
    # Ce fichier ne valide aucun SKU et ne crée aucun enregistrement fiscal.
    actifs = [
        ligne for ligne in skus
        if isinstance(ligne, dict) and ligne.get("actif") == "OUI"
    ]
    champs_export = ("sku_id", "pf_id", "format", "unite_vente")
    if actifs and all(
        isinstance(ligne.get(champ), str) and ligne[champ].strip()
        for ligne in actifs for champ in champs_export
    ):
        from core.registre_qualification_sku import registre_qualification_sku
        try:
            registre = registre_qualification_sku(actifs)
        except ValueError:
            st.warning("Export de revue indisponible : référentiel SKU incohérent.")
        else:
            st.download_button(
                "Télécharger le registre des SKU à qualifier (Markdown)",
                data=registre,
                file_name="revue_tva_sku_actifs.md",
                mime="text/markdown",
                key="ventes_export_revue_tva",
            )
    elif actifs:
        st.info("Export non disponible : détails SKU incomplets.")
    st.warning(
        "Audit uniquement : aucun taux TVA n'a été affecté ni appliqué "
        "aux factures. Une validation juridique par produit et du régime "
        "de l'entreprise reste nécessaire."
    )
