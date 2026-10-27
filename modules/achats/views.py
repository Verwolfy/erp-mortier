"""Écran Achats : contrôle d'accès, réceptions partielles et reprise anti-doublon.

Les RPC Achats restent la seule source des écritures. Une opération non
confirmée est figée en session et reprise avec le même operation_id.
"""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
import logging
from uuid import uuid4

import pandas as pd
import streamlit as st

from config.roles import has_permission
from core.db_service import fetch_data, get_supabase_client
from core.listes_service import get_liste, liste_to_dict
from core.utils import get_local_now
from modules.achats.service import (
    create_commande_achat,
    creer_bon_reception,
    get_bons_reception,
    get_commandes,
    get_lignes_achats,
    get_lignes_bons_reception,
)

_LOG = logging.getLogger(__name__)
_ACTIVE = frozenset({"oui", "true", "1", "actif", "active", "yes"})
_RECEIVABLE = frozenset({"EN_ATTENTE", "PARTIELLEMENT_RECEPTIONNE"})
_REQUIRED_PAYLOAD = {
    "commande": frozenset({"fournisseur_id", "type_achat", "devise", "taux_change",
                             "mode_paiement", "delai_paiement", "date_voulue", "panier"}),
    "reception": frozenset({"commande_achat_id", "date_reception", "controle_conformite",
                              "remarques", "items_recus", "date_peremption"}),
}


def _purchase_access() -> tuple[str, bool] | None:
    """Vérification fraîche en base avant TOUT accès aux achats."""
    try:
        if st.session_state.get("authenticated") is not True:
            return None
        session_user = st.session_state.get("user")
        if not isinstance(session_user, dict):
            return None
        user_id = session_user.get("user_id")
        if not isinstance(user_id, str) or not user_id.strip():
            return None
        response = (get_supabase_client().table("users")
                    .select("user_id,role,actif")
                    .eq("user_id", user_id).limit(1).execute())
        records = response.data or []
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
        if has_permission(role, "Achats", "lecture") is not True:
            return None
        return user_id, has_permission(role, "Achats", "ecriture") is True
    except Exception as exc:
        _LOG.warning("Autorisation Achats non vérifiable (%s)", type(exc).__name__)
        return None


def _cart_key(user_id: str) -> str:
    return f"panier_achats_{user_id}"


def _operation_key(kind: str, user_id: str) -> str:
    if kind not in _REQUIRED_PAYLOAD:
        raise ValueError("Opération Achats inconnue")
    return f"achats_{kind}_{user_id}"


def _execute_operation(kind: str, user_id: str) -> None:
    """Reprend le même payload avec le même identifiant, sans nouvelle saisie."""
    record = st.session_state[_operation_key(kind, user_id)]
    if record["status"] == "confirmed":
        return
    try:
        if kind == "commande":
            doc_id = create_commande_achat(**deepcopy(record["payload"]),
                                           operation_id=record["operation_id"])
        else:
            doc_id = creer_bon_reception(**deepcopy(record["payload"]),
                                         operation_id=record["operation_id"])
        if not isinstance(doc_id, str) or not doc_id.strip():
            raise RuntimeError("Réponse documentaire absente")
    except (ValueError, PermissionError):
        # Ces exceptions sont émises AVANT l'appel RPC dans le service Achats.
        del st.session_state[_operation_key(kind, user_id)]
        st.error("Opération refusée avant enregistrement. Corrigez les données ou vos droits.")
        return
    except Exception as exc:
        # Un timeout peut survenir après le commit PostgreSQL : conserver le dossier.
        _LOG.warning("Transaction Achats non confirmée (%s)", type(exc).__name__)
        record["status"] = "uncertain"
        st.error("Opération non confirmée. Vérifiez son résultat avant de réessayer.")
        st.code(record["operation_id"])
        return

    record["status"] = "confirmed"
    record["document_id"] = doc_id
    if kind == "commande":
        st.session_state[_cart_key(user_id)] = []
    st.rerun()


def _start_operation(kind: str, user_id: str, payload: dict) -> None:
    """Crée le dossier de reprise AVANT la première tentative."""
    key = _operation_key(kind, user_id)
    if key in st.session_state:
        st.error("Une opération existe déjà : utilisez son dossier de reprise.")
        return
    st.session_state[key] = {
        "status": "uncertain",
        "operation_id": f"ACH-UI-{uuid4().hex}",
        "payload": deepcopy(payload),
    }
    _execute_operation(kind, user_id)


def _pending_panel(kind: str, user_id: str) -> bool:
    """Bloque toute nouvelle saisie tant que l'opération n'est pas traitée."""
    key = _operation_key(kind, user_id)
    if key not in st.session_state:
        return False
    record = st.session_state[key]
    valid = (isinstance(record, dict)
             and record.get("status") in {"uncertain", "confirmed"}
             and isinstance(record.get("operation_id"), str)
             and record["operation_id"].startswith("ACH-UI-")
             and isinstance(record.get("payload"), dict)
             and _REQUIRED_PAYLOAD[kind].issubset(record["payload"])
             and (record["status"] != "confirmed" or
                  (isinstance(record.get("document_id"), str) and bool(record["document_id"]))))
    if not valid:
        st.error("Dossier de reprise incorrect : demander une vérification à l'administrateur.")
        return True
    st.code(record["operation_id"])
    if record["status"] == "uncertain":
        st.warning("Transaction non confirmée. Ne créez pas une seconde opération identique.")
        st.info("La reprise réutilise exactement le même document, les mêmes quantités et le même identifiant.")
        if st.button("Réessayer la même opération", key=f"achat_retry_{kind}_{user_id}", on_click=_mark_achats_activity):
            _execute_operation(kind, user_id)
    else:
        st.success(f"{('Commande' if kind == 'commande' else 'Réception')} "
                   f"{record['document_id']} confirmée.")
        if st.button("Préparer une nouvelle opération", key=f"achat_new_{kind}_{user_id}", on_click=_mark_achats_activity):
            del st.session_state[key]
            st.rerun()
    return True


def _decimal_positive(value, label: str, *, allow_zero: bool = False) -> Decimal:
    try:
        val = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{label} non numérique") from exc
    if not val.is_finite() or val >= Decimal("1e15") or (val < 0 if allow_zero else val <= 0):
        raise ValueError(f"{label} invalide")
    return val


def _remaining_quantities(cmd_id: str, lines: pd.DataFrame, brs: pd.DataFrame) -> list[dict]:
    """Calcule le solde à recevoir par MP, y compris après plusieurs BR.

    L'état affiché est informatif ; le SQL 004 effectue le contrôle définitif
    sous verrou au moment de la transaction.
    """
    if lines.empty or not {"mp_id", "qte_totale", "prix_unitaire"}.issubset(lines.columns):
        raise ValueError("Commande sans lignes valides")
    aggregated: dict[str, dict] = {}
    for _, line in lines.iterrows():
        mp = line["mp_id"]
        if not isinstance(mp, str) or not mp.strip():
            raise ValueError("Matière absente sur une ligne de commande")
        qty = _decimal_positive(line["qte_totale"], "Quantité commandée")
        price = _decimal_positive(line["prix_unitaire"], "Prix unitaire", allow_zero=True)
        target = aggregated.setdefault(mp, {"mp_id": mp, "ordered": Decimal(0),
                                            "received": Decimal(0), "cost": Decimal(0)})
        target["ordered"] += qty
        target["cost"] += qty * price
    if not brs.empty:
        if not {"bon_reception_id", "commande_achat_id"}.issubset(brs.columns):
            raise ValueError("Historique des bons de réception incomplet")
        related = brs[brs["commande_achat_id"] == cmd_id]
        for _, br in related.iterrows():
            received_lines = get_lignes_bons_reception(br["bon_reception_id"])
            if received_lines.empty or not {"mp_id", "quantite_recue"}.issubset(received_lines.columns):
                raise ValueError("Historique des réceptions incomplet")
            for _, line in received_lines.iterrows():
                mp = line["mp_id"]
                if mp not in aggregated:
                    raise ValueError("Réception d'une matière absente de la commande")
                aggregated[mp]["received"] += _decimal_positive(line["quantite_recue"],
                                                                  "Quantité déjà reçue")
    result = []
    for item in aggregated.values():
        remaining = item["ordered"] - item["received"]
        if remaining < 0:
            raise ValueError("Historique incohérent : quantité reçue supérieure à la commande")
        if remaining > 0:
            result.append({"mp_id": item["mp_id"], "ordered": float(item["ordered"]),
                           "received": float(item["received"]), "remaining": float(remaining),
                           "prix_unitaire": float(item["cost"] / item["ordered"])})
    return result


def get_fournisseurs_actifs():
    df = pd.DataFrame(fetch_data("fournisseurs"))
    return df[df["actif"] == "OUI"] if not df.empty and "actif" in df.columns else pd.DataFrame()


def get_mp_actives():
    df = pd.DataFrame(fetch_data("matieres_premieres"))
    return df[df["actif"] == "OUI"] if not df.empty and "actif" in df.columns else pd.DataFrame()


def _mark_achats_activity() -> None:
    """Signale une interaction Achats sans renouveler la session."""
    st.session_state["_erp_achats_interacted"] = True


def show_achats_page():
    st.title("🛒 Achats & Approvisionnements")
    access = _purchase_access()
    if access is None:
        st.error("Accès Achats refusé ou session expirée.")
        return
    user_id, can_write = access
    st.session_state.setdefault(_cart_key(user_id), [])
    tab1, tab2, tab3 = st.tabs(["➕ Nouvelle Commande", "📦 Réception & Entrée Stock", "📋 Historique & Suivi"])

    # --- COMMANDE FOURNISSEUR ---
    with tab1:
        if not can_write:
            st.info("🔒 Mode lecture seule.")
        elif _pending_panel("commande", user_id):
            pass
        else:
            df_fournisseurs = get_fournisseurs_actifs()
            df_mp = get_mp_actives()
            if df_fournisseurs.empty or df_mp.empty:
                st.warning("Configurez d'abord les fournisseurs et matières premières actifs.")
            else:
                st.subheader("1. Informations Fournisseur")
                col1, col2 = st.columns(2)
                liste_fournisseurs = {row["fournisseur_id"]: f"{row['fournisseur_id']} - {row['nom']}"
                                     for _, row in df_fournisseurs.iterrows()}
                fournisseur_id = col1.selectbox("Fournisseur", options=list(liste_fournisseurs),
                                                format_func=lambda x: liste_fournisseurs[x])
                type_achat = col2.selectbox("Type d'achat", ["Matière Première", "Emballage", "Frais Généraux"])
                col3, col4, col5 = st.columns(3)
                dict_devise = liste_to_dict(get_liste("Devise")) or {"DZD": "DZD", "EUR": "EUR", "USD": "USD"}
                devise = col3.selectbox("Devise", options=list(dict_devise),
                                       format_func=lambda x: dict_devise.get(x, x))
                # Les prix du panier sont saisis dans la devise selectionnee.
                currency_key = f"achats_panier_devise_{user_id}"
                previous_currency = st.session_state.get(currency_key)
                if previous_currency is not None and previous_currency != devise:
                    if st.session_state[_cart_key(user_id)]:
                        st.session_state[_cart_key(user_id)] = []
                        st.warning("Devise modifiee : panier efface pour eviter de reutiliser des prix dans la mauvaise devise.")
                st.session_state[currency_key] = devise
                taux_change = col4.number_input(
                     "Taux (DZD pour 1 unité de devise)",
                     min_value=0.000001, value=1.0, step=0.1,
                     disabled=str(devise).upper() == "DZD",
                     key=f"achat_taux_{str(devise).upper()}")
                if str(devise).upper() == "DZD":
                    taux_change = 1.0
                st.caption("Exemple : 1 EUR = 150 DZD → taux = 150. La valorisation du stock est toujours en DZD.")
                date_voulue = col5.date_input("Date de livraison souhaitée")
                st.divider()
                st.subheader("2. Lignes de Commande")
                with st.expander("➕ Ajouter un article", expanded=True):
                    c_mp, c_qte, c_prix, c_btn = st.columns([3, 1, 1, 1])
                    liste_mp = {row["mp_id"]: f"{row['mp_id']} - {row['nom']}" for _, row in df_mp.iterrows()}
                    mp_choisie = c_mp.selectbox("Article", options=list(liste_mp),
                                               format_func=lambda x: liste_mp[x])
                    qte = c_qte.number_input("Quantité en unité de stock", min_value=0.001, step=1.0)
                    prix_u = c_prix.number_input(f"Prix unitaire ({devise})", min_value=0.0, step=1.0)
                    if c_btn.button("Ajouter", use_container_width=True):
                        mp_row = df_mp[df_mp["mp_id"] == mp_choisie].iloc[0]
                        unit = str(mp_row.get("unite_stock") or "Unité")
                        st.session_state[_cart_key(user_id)].append({
                            "mp_id": mp_choisie, "nom_article": liste_mp[mp_choisie],
                            "unite_cond": unit, "qte_cond": qte, "qte_totale": qte,
                            "prix_unitaire": prix_u, "total_devise": qte * prix_u,
                        })
                        st.rerun()
                if st.session_state[_cart_key(user_id)]:
                    df_panier = pd.DataFrame(st.session_state[_cart_key(user_id)])
                    st.dataframe(df_panier[["mp_id", "nom_article", "qte_totale", "prix_unitaire", "total_devise"]],
                                 use_container_width=True)
                    # Apercu indicatif : PostgreSQL recalcule le total avant d'ecrire.
                    total_devise = sum((Decimal(str(x["total_devise"]))
                                         for x in st.session_state[_cart_key(user_id)]), Decimal(0))
                    total_local = total_devise * Decimal(str(taux_change))
                    st.caption(f"Total : {total_devise:,.2f} {devise} = {total_local:,.2f} DZD (taux saisi)")
                    if st.button("🗑️ Vider", on_click=_mark_achats_activity):
                        st.session_state[_cart_key(user_id)] = []
                        st.rerun()
                else:
                    st.info("Aucun article dans la commande.")
                st.divider()
                st.subheader("3. Modalités & Validation")
                c_mode, c_delai, c_valider = st.columns(3)
                dict_mode = liste_to_dict(get_liste("ModePaiement")) or {
                    "Virement": "Virement", "Chèque": "Chèque", "Espèces": "Espèces"}
                mode = c_mode.selectbox("Mode de paiement", options=list(dict_mode),
                                        format_func=lambda x: dict_mode.get(x, x))
                dict_delai = liste_to_dict(get_liste("ConditionPaiement")) or {
                    "Comptant": "Comptant", "30 jours": "30 jours", "60 jours": "60 jours"}
                delai = c_delai.selectbox("Délai de paiement", options=list(dict_delai),
                                          format_func=lambda x: dict_delai.get(x, x))
                if c_valider.button("✅ Générer la commande", type="primary", use_container_width=True,
                                    disabled=not st.session_state[_cart_key(user_id)]):
                    payload = {"fournisseur_id": fournisseur_id, "type_achat": type_achat,
                               "devise": devise, "taux_change": taux_change,
                               "mode_paiement": mode, "delai_paiement": delai,
                               "date_voulue": str(date_voulue),
                               "panier": deepcopy(st.session_state[_cart_key(user_id)])}
                    _start_operation("commande", user_id, payload)

    # --- BON DE RÉCEPTION ---
    with tab2:
        st.subheader("Générer un bon de réception (BR)")
        if not can_write:
            st.info("🔒 Mode lecture seule.")
        elif _pending_panel("reception", user_id):
            pass
        else:
            df_commandes = get_commandes()
            if df_commandes.empty or "statut" not in df_commandes.columns:
                st.info("Aucune commande réceptionnable.")
            else:
                available = df_commandes[df_commandes["statut"].isin(_RECEIVABLE)]
                if available.empty:
                    st.info("Aucune commande en attente ou partiellement réceptionnée.")
                else:
                    labels = {row["commande_achat_id"]:
                              f"{row['commande_achat_id']} - {row['fournisseur_id']} ({row['date_commande']})"
                              for _, row in available.iterrows()}
                    selected = st.selectbox("Commande à réceptionner", options=list(labels),
                                            format_func=lambda x: labels[x], on_change=_mark_achats_activity)
                    if selected:
                        try:
                            lines = get_lignes_achats(selected)
                            balances = _remaining_quantities(selected, lines, get_bons_reception())
                            selected_order = available[available["commande_achat_id"] == selected].iloc[0]
                            order_currency = str(selected_order.get("devise") or "").strip().upper()
                            order_exchange = _decimal_positive(selected_order.get("taux_change"), "Taux de commande")
                            if not order_currency or (order_currency == "DZD" and order_exchange != 1):
                                raise ValueError("Devise et taux de commande non coherents")
                        except (ValueError, KeyError) as exc:
                            _LOG.warning("Solde BC incohérent (%s)", type(exc).__name__)
                            st.error("Historique de cette commande incomplet : réception bloquée.")
                        else:
                            if not balances:
                                st.info("Toutes les quantités de cette commande sont déjà réceptionnées.")
                            else:
                                st.markdown("**Quantités restant à réceptionner**")
                                st.caption(f"Prix de commande : {order_currency} ; valorisation des entrees en DZD "
                                            f"au taux historique {order_exchange}. Prix non modifiable a la reception.")
                                items_recus = []
                                with st.form(f"form_reception_{selected}"):
                                    c1, c2 = st.columns(2)
                                    date_rec = c1.date_input("Date de réception", value=get_local_now())
                                    conformite = c2.radio("Contrôle conformité",
                                                          ["CONFORME", "RESERVE", "NON_CONFORME"],
                                                          horizontal=True)
                                    c3, c4 = st.columns(2)
                                    remarques = c3.text_input("Remarques / Observation")
                                    peremption = c4.date_input("Date de péremption")
                                    st.divider()
                                    for row in balances:
                                        remaining = row["remaining"]
                                        qte = st.number_input(
                                            f"{row['mp_id']} (commandé {row['ordered']}, déjà reçu "
                                            f"{row['received']}, solde {remaining})",
                                            min_value=0.0, max_value=remaining,
                                            value=remaining, step=1.0,
                                            key=f"ach_rec_{selected}_{row['mp_id']}")
                                        if qte > 0:
                                            stock_unit_cost = (Decimal(str(row["prix_unitaire"])) * order_exchange)
                                            st.caption(f"Cout d'entree estime : {stock_unit_cost:,.4f} DZD / unite de stock")
                                            items_recus.append({"mp_id": row["mp_id"],
                                                                "quantite_recue": qte,
                                                                "prix_unitaire": row["prix_unitaire"]})
                                    submitted = st.form_submit_button("📦 Valider la réception", type="primary", on_click=_mark_achats_activity)
                                if submitted:
                                    if conformite != "CONFORME":
                                        st.error("Réception non conforme/réservée : aucun stock créé. "
                                                 "La quarantaine n'est pas encore disponible.")
                                    elif not items_recus:
                                        st.error("Indiquez au moins une quantité positive.")
                                    else:
                                        _start_operation("reception", user_id, {
                                            "commande_achat_id": selected,
                                            "date_reception": str(date_rec),
                                            "controle_conformite": "OUI",
                                            "remarques": remarques,
                                            "items_recus": deepcopy(items_recus),
                                            "date_peremption": str(peremption),
                                        })

    # --- HISTORIQUE ---
    with tab3:
        st.subheader("Commandes d'Achats")
        commandes = get_commandes()
        if not commandes.empty:
            st.dataframe(commandes.sort_values(by="date_commande", ascending=False),
                         use_container_width=True, hide_index=True)
        else:
            st.info("Aucune commande enregistrée.")
        st.divider()
        st.subheader("Bons de réception")
        receptions = get_bons_reception()
        if not receptions.empty:
            st.dataframe(receptions.sort_values(by="date_reception", ascending=False),
                         use_container_width=True, hide_index=True)
        else:
            st.info("Aucun bon de réception enregistré.")
