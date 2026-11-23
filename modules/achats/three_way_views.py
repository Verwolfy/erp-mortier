"""ERP-063 — Dossier de rapprochement 3 voies, lecture seule."""
from __future__ import annotations

import logging

import pandas as pd
import streamlit as st

from modules.achats.three_way_match import ThreeWayError, load_supplier_invoice_match

_LOG = logging.getLogger(__name__)


def show_three_way_match() -> None:
    st.subheader("Rapprochement fournisseur : BC / Réception / Facture")
    st.caption(
        "Contrôle documentaire en lecture seule : matières, quantités, prix, "
        "HT/TVA/TTC et cumul des factures liées. Une concordance ne valide "
        "ni la TVA, ni la facture, ni un paiement. Les lectures ne constituent "
        "pas une photographie transactionnelle."
    )
    ref = st.text_input(
        "Référence exacte de la facture fournisseur",
        max_chars=128, key="erp63_invoice_reference",
    )
    if not st.button("Vérifier les trois pièces (lecture seule)",
                     key="erp63_match_execute"):
        return
    try:
        result = load_supplier_invoice_match(ref.strip())
    except (ThreeWayError, PermissionError, ValueError, RuntimeError,
            TypeError, KeyError) as exc:
        _LOG.warning("Contrôle fournisseur indisponible (%s)", type(exc).__name__)
        st.error("Pièces non vérifiables : aucun rapprochement partiel affiché.")
        return
    if result["blocages"]:
        st.error("Rapprochement bloqué : anomalies ou pièces manquantes.")
        for message in result["blocages"][:30]:
            st.warning(message)
    else:
        st.success("Concordance documentaire des éléments consultés.")
    st.warning(
        "NON PAYABLE — résultat de gestion. Signature fournisseur, "
        "visa interne, fiscalité et contrôle de paiement non homologués."
    )
    st.dataframe(pd.DataFrame(result["lignes"]),
                 use_container_width=True, hide_index=True)
    fmt = st.selectbox(
        "Format de l'état",
        ("Excel (.xlsx)", "CSV (.csv)", "PDF (.pdf)"),
        key="erp63_export_choice",
    )
    from core.export_formats import build_export, export_filename, ExportError
    fields = [
        "mp_id", "quantite_bc", "quantite_recue_conforme",
        "quantite_facture", "quantite_facturee_cumulee",
        "prix_bc_dzd", "prix_facture_dzd", "constat",
    ]
    try:
        ext = fmt.split("(")[1].split(")")[0].lstrip(".")
        rows = result["lignes"]
        if not rows:
            st.info("Aucune ligne rapprochable.")
            return
        payload, mime, ext = build_export(
            rows, fields, fmt=ext,
            title=f"Contrôle BC/BR/FF : {result['facture_fournisseur_id']}",
            warning="NON PAYABLE / NON FISCAL / NON SIGNÉ — consultation seulement",
        )
    except (ExportError, ValueError, TypeError):
        st.error("Export impossible : données ou format non vérifiables.")
        return
    st.download_button(
        "Télécharger le dossier de contrôle",
        data=payload, mime=mime,
        file_name=export_filename(
            f"ERP63_controle_{result['facture_fournisseur_id']}", ext),
        key="erp63_match_download",
    )
