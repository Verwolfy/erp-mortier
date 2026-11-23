"""Actions de ligne pour les documents ERP enregistrés : lecture seule.

Les copies restent NON EMISES / NON SIGNEES, même pour une facture.
Pas d'envoi, de visa, de paiement ni d'écriture stock.
"""
from __future__ import annotations

import logging

import pandas as pd
import streamlit as st

_LOG = logging.getLogger(__name__)
ACTIONS = ("consulter", "imprimer", "pdf")


def _key(scope: str, user_id: str, suffix: str) -> str:
    return f"erp_docs_{scope}_{user_id}_{suffix}"


def _choose(scope: str, user_id: str, action: str, identifier: str) -> None:
    if action in ACTIONS and isinstance(identifier, str) and identifier:
        st.session_state[_key(scope, user_id, "selected")] = (action, identifier)


def _clicked(scope: str, user_id: str, action: str,
             ids: tuple[str, ...], click_key: str) -> None:
    event = st.session_state.get(click_key)
    try:
        row = event["row"]
    except (KeyError, IndexError, TypeError):
        return
    if type(row) is not int or not 0 <= row < len(ids):
        return
    _choose(scope, user_id, action, ids[row])


def _show_selected(kind: str, user_id: str, scope: str,
                   ids: tuple[str, ...]) -> None:
    key = _key(scope, user_id, "selected")
    selected = st.session_state.get(key)
    if not (isinstance(selected, tuple) and len(selected) == 2
            and selected[0] in ACTIONS and selected[1] in ids):
        st.session_state.pop(key, None)
        return
    action, identifier = selected
    from modules.documents.erp_print import (
        OperationPrintError, load_operation_snapshot, render_operation_pdf,
    )
    st.markdown(f"**{kind} : {identifier}**")
    st.warning("COPIE NON EMISE / NON SIGNEE. Les factures ne constituent "
               "pas des documents fiscaux homologués.")
    try:
        snapshot = load_operation_snapshot(kind, identifier)
        if "NON ÉMIS" not in str(snapshot.get("warning", "")):
            raise OperationPrintError("Statut documentaire absent")
        if action == "consulter":
            st.caption(f"Date : {snapshot['date']} · Tiers : {snapshot['partner']}")
            for label, value in snapshot["meta"] + snapshot["totals"]:
                st.write(f"**{label} :** {value}")
            st.dataframe(pd.DataFrame(snapshot["lines"]),
                         use_container_width=True, hide_index=True)
        else:
            pdf = render_operation_pdf(snapshot)
            if not isinstance(pdf, bytes) or not pdf.startswith(b"%PDF"):
                raise OperationPrintError("PDF non vérifiable")
            if action == "imprimer":
                st.info("Utilisez le lecteur PDF pour imprimer ou téléchargez "
                        "la copie puis Ctrl+P.")
                if callable(getattr(st, "pdf", None)):
                    try:
                        st.pdf(pdf, height=650)
                    except Exception as exc:
                        _LOG.warning("Lecteur PDF indisponible (%s)", type(exc).__name__)
                        st.caption("Aperçu intégré indisponible : utilisez le PDF téléchargé.")
            from core.export_formats import export_filename
            st.download_button(
                "Télécharger le PDF — copie non émise",
                data=pdf, mime="application/pdf",
                file_name=export_filename(f"Copie_{identifier}", "pdf"),
                key=_key(scope, user_id, "download"),
            )
    except (OperationPrintError, PermissionError, ValueError,
            RuntimeError, TypeError, KeyError, ImportError) as exc:
        _LOG.warning("Copie %s indisponible (%s)", identifier, type(exc).__name__)
        st.error("Document ou lignes non vérifiables : aucune copie partielle.")
    if st.button("Fermer la consultation", key=_key(scope, user_id, "close")):
        st.session_state.pop(key, None)
        st.rerun()


def show_recorded_documents(rows, *, kind: str, id_column: str,
                            user_id: str, scope: str) -> None:
    """Affiche Consulter, Imprimer, PDF après l'identifiant de chaque document.

    Ne lit aucune table avant un clic sur une ligne. Les droits sont revérifiés
    par load_operation_snapshot à chaque consultation.
    """
    from modules.documents.erp_print import KINDS
    if kind not in KINDS:
        raise ValueError("Type documentaire sans moteur d'impression vérifié")
    frame = (rows.copy() if isinstance(rows, pd.DataFrame)
             else pd.DataFrame(rows)).reset_index(drop=True)
    if frame.empty:
        st.info("Aucun document dans cette vue.")
        return
    if id_column not in frame:
        st.error("Identifiant documentaire manquant : actions désactivées.")
        st.dataframe(frame, use_container_width=True, hide_index=True)
        return
    ids = tuple(frame[id_column].tolist())
    if (any(not isinstance(x, str) or not x for x in ids)
            or len(set(ids)) != len(ids)):
        st.error("Références invalides ou dupliquées : actions désactivées.")
        st.dataframe(frame, use_container_width=True, hide_index=True)
        return
    ButtonColumn = getattr(getattr(st, "column_config", None), "ButtonColumn", None)
    if callable(ButtonColumn):
        specs = (
            ("Consulter", ":material/visibility: Voir", "consulter"),
            ("Imprimer", ":material/print: Imprimer", "imprimer"),
            ("PDF", ":material/picture_as_pdf: PDF", "pdf"),
        )
        visible = frame.copy()
        configs = {}
        for label, caption, action in specs:
            visible[label] = caption
            click_key = _key(scope, user_id, f"click_{action}")
            configs[label] = ButtonColumn(
                label, width="small", type="tertiary", pinned=True,
                on_click=_clicked, args=(scope, user_id, action, ids, click_key),
                key=click_key,
            )
        st.dataframe(
            visible,
            column_order=[id_column, *[x[0] for x in specs],
                          *[name for name in frame if name != id_column]],
            column_config=configs, hide_index=True, use_container_width=True,
        )
    else:
        st.dataframe(frame, use_container_width=True, hide_index=True)
        st.caption("Actions affichées sous le tableau pour cette version de Streamlit.")
        for identifier in ids:
            columns = st.columns([3, 1, 1, 1])
            columns[0].caption(identifier)
            for column, action, caption in zip(columns[1:], ACTIONS,
                                               ("👁️ Voir", "🖨️ Imprimer", "📄 PDF")):
                if column.button(caption, key=_key(scope, user_id, f"{action}_{identifier}")):
                    _choose(scope, user_id, action, identifier)
    _show_selected(kind, user_id, scope, ids)
