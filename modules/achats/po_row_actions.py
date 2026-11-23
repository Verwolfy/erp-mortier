"""Actions par ligne du tableau des commandes fournisseurs (lecture seule).

Les PDF sont des COPIES NON EMISES / NON SIGNEES. Aucun envoi, visa ni
transaction fournisseur n'est effectué. Le clic ne choisit qu'une référence
présente dans la page d'historique déjà autorisée par le contrôle RBAC.
"""
from __future__ import annotations

import logging

import pandas as pd
import streamlit as st

_LOG = logging.getLogger(__name__)
_ACTIONS = ("consulter", "imprimer", "pdf")


def _selection_key(user_id: str) -> str:
    return f"achats_po_selected_{user_id}"


def _activate(user_id: str, action: str, order_id: str) -> None:
    if action in _ACTIONS and isinstance(order_id, str) and order_id:
        st.session_state[_selection_key(user_id)] = (action, order_id)


def _on_click(user_id: str, action: str, ids: tuple[str, ...], click_key: str) -> None:
    """La ligne provient du tableau affiché, jamais d'un champ référence libre."""
    event = st.session_state.get(click_key)
    try:
        row = event["row"]
    except (TypeError, KeyError, IndexError):
        return
    if isinstance(row, bool) or not isinstance(row, int) or not 0 <= row < len(ids):
        return
    _activate(user_id, action, ids[row])


def _show_selection(user_id: str, available_ids: tuple[str, ...]) -> None:
    selected = st.session_state.get(_selection_key(user_id))
    if not (isinstance(selected, tuple) and len(selected) == 2
            and selected[0] in _ACTIONS and selected[1] in available_ids):
        st.session_state.pop(_selection_key(user_id), None)
        return

    action, po_id = selected
    # Lazy import + contrôle strict à chaque affichage. Pas de cache de PDF partagé.
    from modules.documents.erp_print import (
        OperationPrintError, load_operation_snapshot, render_operation_pdf,
    )
    st.markdown(f"**Bon de commande :** `{po_id}`")
    st.warning("COPIE NON ÉMISE / NON SIGNÉE — aucune signature ni transmission fournisseur.")

    try:
        snapshot = load_operation_snapshot("Commande fournisseur", po_id)
        if "NON ÉMISE" not in snapshot.get("warning", ""):
            raise OperationPrintError("Statut documentaire non confirmé")
        if action == "consulter":
            st.caption(f"Référence : {snapshot['id']} · Date : {snapshot['date']}"
                       f" · Fournisseur : {snapshot['partner']}")
            for label, value in snapshot["meta"] + snapshot["totals"]:
                st.write(f"**{label} :** {value}")
            st.dataframe(pd.DataFrame(snapshot["lines"]),
                         use_container_width=True, hide_index=True)
        else:
            payload = render_operation_pdf(snapshot)
            if not isinstance(payload, bytes) or not payload.startswith(b"%PDF"):
                raise OperationPrintError("PDF invalide")
            if action == "imprimer":
                st.info("Aperçu pour impression : utilisez l'icône imprimer du lecteur PDF "
                        "ou ouvrez le PDF téléchargé et faites Ctrl+P.")
                if callable(getattr(st, "pdf", None)):
                    try:
                        st.pdf(payload, height=650)
                    except Exception as exc:
                        # Le lecteur PDF est optionnel (extra streamlit-pdf).
                        _LOG.warning("Lecteur PDF absent (%s)", type(exc).__name__)
                        st.caption("Aperçu intégré indisponible : utilisez le téléchargement ci-dessous.")
            from core.export_formats import export_filename
            st.download_button(
                "📄 Télécharger la copie PDF — NON ÉMISE",
                data=payload, mime="application/pdf",
                file_name=export_filename(f"BC_consultation_{snapshot['id']}", "pdf"),
                key=f"achats_po_download_{user_id}",
            )
    except (OperationPrintError, PermissionError, ValueError,
            RuntimeError, TypeError, KeyError) as exc:
        _LOG.warning("BC %s indisponible (%s)", po_id, type(exc).__name__)
        st.error("Bon de commande ou lignes non vérifiables : aucune copie partielle affichée.")

    if st.button("Fermer le détail du bon de commande", key=f"achats_po_close_{user_id}"):
        st.session_state.pop(_selection_key(user_id), None)
        st.rerun()


def show_purchase_orders_with_actions(rows: list[dict], user_id: str) -> None:
    """Affiche l'historique avec 3 actions immédiates, sans saisie de référence.

    Exige le chargement préalable de la page 50 lignes max par le module Achats.
    Compatible avec les tableaux Streamlit >= 1.59, repli disponible sinon.
    """
    frame = pd.DataFrame(rows).reset_index(drop=True)
    ids = tuple(frame["commande_achat_id"].tolist()) if "commande_achat_id" in frame else ()
    if (not ids or any(not isinstance(x, str) or not x for x in ids)
            or len(set(ids)) != len(ids)):
        st.error("Références de commandes absentes ou ambiguës ; actions indisponibles.")
        st.dataframe(frame, use_container_width=True, hide_index=True)
        return

    button_col = getattr(getattr(st, "column_config", None), "ButtonColumn", None)
    if callable(button_col):
        labels = {
            "Consulter": (":material/visibility: Voir", "consulter"),
            "Imprimer": (":material/print: Imprimer", "imprimer"),
            "PDF": (":material/picture_as_pdf: PDF", "pdf"),
        }
        display = frame.copy()
        configs = {}
        for col, (caption, action) in labels.items():
            display[col] = caption
            click_key = f"achats_po_click_{action}_{user_id}"
            configs[col] = button_col(
                col, width="small", type="tertiary", pinned=True,
                on_click=_on_click, args=(user_id, action, ids, click_key), key=click_key,
            )
        columns = ["commande_achat_id", *labels, *[c for c in frame if c != "commande_achat_id"]]
        st.dataframe(display, column_order=columns, column_config=configs,
                     use_container_width=True, hide_index=True)
    else:
        # Repli sans HTML/script : compatible avec une ancienne version de Streamlit.
        st.warning("Streamlit 1.59+ recommandé pour les boutons intégrés au tableau.")
        st.dataframe(frame, use_container_width=True, hide_index=True)
        for po_id in ids:
            col_ref, col_voir, col_print, col_pdf = st.columns([3, 1, 1, 1])
            col_ref.caption(po_id)
            for col, title, action in (
                (col_voir, "👁️ Voir", "consulter"),
                (col_print, "🖨️ Imprimer", "imprimer"),
                (col_pdf, "📄 PDF", "pdf"),
            ):
                if col.button(title, key=f"achats_po_fallback_{action}_{user_id}_{po_id}"):
                    _activate(user_id, action, po_id)

    _show_selection(user_id, ids)
