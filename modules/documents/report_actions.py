"""Actions Consulter, Imprimer et PDF pour rapports non persistés.

Le rapport est calculé et autorisé PAR L'APPELANT à partir du registre réel.
La copie imprimable ne crée ni écriture ni état comptable certifié.
"""
from __future__ import annotations

import logging

import pandas as pd
import streamlit as st

_LOG = logging.getLogger(__name__)


def show_report_actions(frame: pd.DataFrame, *, columns: list[str],
                        title: str, period: str, scope: str) -> None:
    """Actions d'un état de gestion déjà calculé, non d'une pièce ERP émise."""
    if not isinstance(frame, pd.DataFrame) or not isinstance(columns, list):
        raise ValueError("État périodique non vérifiable")
    if frame.empty:
        st.info("Aucune ligne sur la période : aucun document à imprimer.")
        st.dataframe(frame, use_container_width=True, hide_index=True)
        return
    if not set(columns).issubset(frame.columns):
        raise ValueError("Colonnes du rapport incomplètes")

    c_view, c_print, c_pdf = st.columns(3)
    state_key = f"erp_report_action_{scope}"
    if c_view.button("👁️ Consulter", key=f"erp_report_view_{scope}"):
        st.session_state[state_key] = "consulter"
    if c_print.button("🖨️ Imprimer", key=f"erp_report_print_{scope}"):
        st.session_state[state_key] = "imprimer"

    warning = ("ÉTAT DE GESTION NON CERTIFIÉ SCF — stock initial reconstitué, "
               "aucune opération de stock ajoutée ni comptabilisée.")
    from core.export_formats import build_export, export_filename, ExportError
    try:
        pdf, mime, ext = build_export(
            frame[columns].to_dict(orient="records"), columns, fmt="pdf",
            title=f"État périodique — {title} — {period}",
            warning=warning,
        )
        if not isinstance(pdf, bytes) or not pdf.startswith(b"%PDF"):
            raise ExportError("Fichier PDF invalide")
    except (ExportError, ValueError, TypeError) as exc:
        _LOG.warning("PDF de l'état indisponible (%s)", type(exc).__name__)
        pdf = None
        c_pdf.button("📄 PDF indisponible", disabled=True,
                     key=f"erp_report_pdf_unavailable_{scope}")
        st.caption("Le PDF nécessite un périmètre plus réduit (250 lignes maximum). "
                   "Excel et CSV restent disponibles.")
    else:
        c_pdf.download_button(
            "📄 PDF", pdf,
            mime=mime, file_name=export_filename(f"Etat_{scope}_{period}", ext),
            key=f"erp_report_pdf_{scope}",
        )
    st.dataframe(frame, use_container_width=True, hide_index=True)

    if st.session_state.get(state_key) == "imprimer":
        st.warning(warning)
        if pdf is None:
            st.info("Aperçu imprimable indisponible : réduire le périmètre de l'état.")
        elif callable(getattr(st, "pdf", None)):
            try:
                st.pdf(pdf, height=650)
            except Exception as exc:
                _LOG.warning("Lecteur PDF impossible (%s)", type(exc).__name__)
                st.caption("Téléchargez le PDF puis imprimez-le avec Ctrl+P.")
        else:
            st.caption("Téléchargez le PDF puis imprimez-le avec Ctrl+P.")
    elif st.session_state.get(state_key) == "consulter":
        st.caption(f"Consultation interne — {period} · {len(frame)} lignes.")
