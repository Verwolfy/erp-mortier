"""ERP-062 — Interface des demandes d'achat (activation explicite seulement).

Cette vue est masquée tant que la migration additive n'est pas homologuée.
Une DA ne produit ni mouvement MP ni commande avant approbation indépendante.
"""
from __future__ import annotations

from copy import deepcopy
from uuid import uuid4
import logging

import pandas as pd
import streamlit as st

from modules.achats.requisitions import (
    PurchaseRequestError, create_request_payload, convert_request_payload,
    list_purchase_requests, purchase_request_lines, purchase_request_action,
)
from core.utils import get_local_now

_LOG = logging.getLogger(__name__)


def _key(actor: str) -> str:
    return f"erp62_da_operation_{actor}"


def _execute(actor: str) -> None:
    record = st.session_state[_key(actor)]
    if record["status"] == "confirmed":
        return
    try:
        result = purchase_request_action(
            record["action"], deepcopy(record["payload"]),
            operation_id=record["operation_id"],
        )
    except (ValueError, PermissionError) as exc:
        _LOG.warning("Demande Achat bloquée avant RPC (%s)", type(exc).__name__)
        st.error("Demande non autorisée ou données incorrectes.")
        return
    except Exception as exc:
        _LOG.warning("Demande Achat incertaine (%s)", type(exc).__name__)
        st.error("Résultat non confirmé. Ne recréez pas de demande : utilisez le même identifiant.")
        st.code(record["operation_id"])
        return
    record["status"] = "confirmed"
    record["result"] = result
    st.rerun()


def _submit(actor: str, action: str, payload: dict) -> None:
    key = _key(actor)
    if key in st.session_state:
        st.error("Un dossier de reprise existe : clôturez-le avant une nouvelle action.")
        return
    st.session_state[key] = {
        "operation_id": f"DA-UI-{uuid4().hex}",
        "action": action,
        "payload": deepcopy(payload),
        "status": "uncertain",
    }
    _execute(actor)


def _pending(actor: str) -> bool:
    key = _key(actor)
    if key not in st.session_state:
        return False
    record = st.session_state[key]
    if not isinstance(record, dict) or not isinstance(record.get("operation_id"), str) \
       or not record["operation_id"].startswith("DA-UI-") \
       or record.get("action") not in {"CREATE", "SUBMIT", "APPROVE", "REJECT", "CONVERT"} \
       or not isinstance(record.get("payload"), dict):
        st.error("Dossier de reprise invalide. Intervention administrateur requise.")
        return True
    st.code(record["operation_id"])
    if record.get("status") == "confirmed":
        result = record["result"]
        st.success(f"Demande {result['demande_id']} : {result['statut']}.")
        if result.get("commande_achat_id"):
            st.info(f"Commande fournisseur : {result['commande_achat_id']}. "
                    "Le PDF de consultation est accessible dans Documents.")
        if st.button("Passer à l'étape suivante", key=f"erp62_clear_{actor}"):
            del st.session_state[key]
            st.rerun()
    else:
        st.warning("Action non confirmée : vérifier le journal avant toute reprise.")
        st.caption("Ne modifiez ni référence, ni quantités, ni auteur. "
                   "La reprise conserve exactement la même opération.")
        if st.button("Reprendre l'opération identique", key=f"erp62_retry_{actor}"):
            _execute(actor)
    return True


def show_purchase_requests(actor: str, can_write: bool) -> None:
    st.subheader("Demandes d'achat — circuit d'approbation")
    st.info(
        "Brouillon → Soumission → Approbation par un second utilisateur "
        "→ Commande fournisseur → Réception. Aucun paiement automatique."
    )
    if _pending(actor):
        return
    try:
        requests = list_purchase_requests()
    except (RuntimeError, PermissionError):
        st.error("Circuit DA non disponible : vérifier la migration et les droits.")
        return
    if requests:
        st.dataframe(pd.DataFrame(requests), use_container_width=True, hide_index=True)
    if not can_write:
        st.info("Consultation uniquement.")
        return
    from modules.achats.views import get_mp_actives, get_fournisseurs_actifs
    with st.expander("Créer une demande d'achat", expanded=not bool(requests)):
        try:
            active_mp = get_mp_actives()
        except Exception as exc:
            _LOG.warning("Articles DA illisibles (%s)", type(exc).__name__)
            st.error("Référentiel matières indisponible.")
            active_mp = pd.DataFrame()
        if active_mp.empty or "mp_id" not in active_mp:
            st.warning("Aucune matière active et qualifiée.")
        else:
            choices = sorted(str(x) for x in active_mp["mp_id"].dropna())
            with st.form("erp62_new_requisition"):
                motivation = st.text_area("Justification du besoin (10 à 1500 caractères)",
                                          max_chars=1500)
                wanted = st.date_input("Date de besoin", value=get_local_now())
                edited = st.data_editor(
                    pd.DataFrame([{"mp_id": choices[0], "quantite": 1.0}]),
                    num_rows="dynamic", hide_index=True,
                    column_config={
                        "mp_id": st.column_config.SelectboxColumn(
                            "Matière", options=choices, required=True),
                        "quantite": st.column_config.NumberColumn(
                            "Quantité en unité de stock", min_value=0.001, required=True),
                    }, key="erp62_lines_editor",
                )
                submit = st.form_submit_button("Enregistrer le brouillon")
            if submit:
                try:
                    payload = create_request_payload(
                        motivation, str(wanted), edited.to_dict("records"),
                    )
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    _submit(actor, "CREATE", payload)
    if not requests:
        return
    choices = {row["demande_id"]: row for row in requests
               if isinstance(row.get("demande_id"), str)}
    selected = st.selectbox("Dossier à traiter", list(choices))
    if not selected:
        return
    record = choices[selected]
    try:
        lines = purchase_request_lines(selected)
    except (RuntimeError, PermissionError, ValueError):
        st.error("Lignes de demande non disponibles. Action bloquée.")
        return
    st.dataframe(pd.DataFrame(lines), use_container_width=True, hide_index=True)
    state = record.get("statut")
    if state == "BROUILLON" and record.get("demandeur_id") == actor:
        if st.button("Soumettre pour approbation", key=f"erp62_submit_{selected}"):
            _submit(actor, "SUBMIT", {"demande_id": selected})
    elif state == "SOUMISE":
        if record.get("demandeur_id") == actor:
            st.warning("Auto-approbation interdite : un second utilisateur actif "
                       "ayant les droits Achats doit prendre la décision.")
        else:
            with st.form(f"erp62_decide_{selected}"):
                comment = st.text_area("Commentaire décision")
                c1, c2 = st.columns(2)
                yes = c1.form_submit_button("Approuver")
                no = c2.form_submit_button("Refuser avec motif")
            if yes or no:
                action = "APPROVE" if yes else "REJECT"
                if no and len(comment.strip()) < 10:
                    st.error("Le refus exige une justification d'au moins 10 caractères.")
                else:
                    _submit(actor, action, {"demande_id": selected,
                                            "commentaire": comment.strip()})
    elif state == "APPROUVEE":
        try:
            suppliers = get_fournisseurs_actifs()
        except Exception:
            suppliers = pd.DataFrame()
        if suppliers.empty or "fournisseur_id" not in suppliers:
            st.error("Aucun fournisseur actif : conversion en BC impossible.")
            return
        with st.form(f"erp62_convert_{selected}"):
            supplier = st.selectbox(
                "Fournisseur actif", suppliers["fournisseur_id"].dropna().tolist())
            st.caption("Les quantités approuvées sont verrouillées. "
                       "Seul le prix d'achat DZD est à renseigner.")
            prices = st.data_editor(
                pd.DataFrame([{
                    "mp_id": row["mp_id"], "quantite": float(row["quantite"]),
                    "prix_unitaire": 0.0,
                } for row in lines]),
                disabled=["mp_id", "quantite"],
                hide_index=True,
                column_config={"prix_unitaire": st.column_config.NumberColumn(
                    "Prix unitaire DZD", min_value=0.0, required=True)},
                key=f"erp62_prices_{selected}",
            )
            wanted = st.date_input("Date livraison souhaitée", value=get_local_now())
            convert = st.form_submit_button("Transformer en commande fournisseur")
        if convert:
            try:
                payload = convert_request_payload(
                    selected, supplier, prices.to_dict("records"), str(wanted),
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                _submit(actor, "CONVERT", payload)
    elif state == "COMMANDEE":
        st.success(f"Commande liée : {record.get('commande_achat_id') or 'non vérifiable'}")
    elif state == "REFUSEE":
        st.warning("Demande refusée : consulter le motif et la piste d'audit.")
