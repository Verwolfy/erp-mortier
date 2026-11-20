"""Centre d'exports accessible aux utilisateurs ERP authentifiés.

Les tables sont lues uniquement APRÈS les contrôles RBAC de core.strict_reads.
Un PDF/Excel/CSV de ce module n'émet aucune pièce fiscale ou comptable.
"""
from __future__ import annotations

import logging
from datetime import date

import streamlit as st

_LOG = logging.getLogger(__name__)


def show_exports_page() -> None:
    st.title("📥 Centre d'exports NEXTGEN")
    if (st.session_state.get("authenticated") is not True
            or not isinstance(st.session_state.get("user"), dict)
            or not st.session_state["user"].get("user_id")):
        st.error("Session ERP authentifiée requise.")
        return
    st.caption(
        "Exports internes au format Excel (.xlsx), CSV UTF-8 (;) et PDF A4. "
        "Charte NEXTGEN : bleu marine, vert et en-tête/pied d'entreprise. "
        "Aucune pièce émise, aucune mutation en base."
    )
    choice = st.selectbox(
        "Type d'export", ["Registres métier", "Documents administratifs et impressions"],
        key="ng_export_section",
    )
    if choice == "Documents administratifs et impressions":
        from modules.documents.views import show_documents_page
        show_documents_page()
        return

    from core.export_catalogue import REPORTS, report_choices, read_report
    from core.export_formats import build_export, export_filename, ExportError
    from core.strict_reads import DataReadError

    families = list(dict.fromkeys(r.family for r in REPORTS.values()))
    family = st.selectbox("Famille métier", families, key="ng_export_family")
    options = report_choices(family)
    key = st.selectbox("Registre à exporter", list(options),
                       format_func=lambda x: options[x], key="ng_export_registry")
    spec = REPORTS[key]
    st.caption(f"Source de données : {spec.table}. Champs autorisés : "
               + ", ".join(spec.columns))
    with st.form("ng_export_form"):
        period = st.checkbox("Limiter à une période", value=False,
                             disabled=spec.date_column is None,
                             key="ng_export_use_period")
        col1, col2 = st.columns(2)
        start = col1.date_input("Du", value=date.today().replace(day=1),
                                disabled=not period)
        end = col2.date_input("Au", value=date.today(), disabled=not period)
        fmt = st.selectbox(
            "Format de téléchargement",
            ["Excel (.xlsx)", "CSV (.csv)", "PDF (.pdf)"],
            key="ng_export_format",
        )
        submit = st.form_submit_button("Préparer le téléchargement", type="primary")
    st.caption(
        "Lecture contrôlée et exhaustive (10 000 lignes maximum, PDF 250). "
        "Fichier produit seulement sur demande, sans stockage serveur. "
        "Les données financières et fiscales sont des copies de consultation, "
        "jamais des pièces officielles."
    )
    if not submit:
        return
    extension = fmt.split("(")[1].split(")")[0].lstrip(".")
    try:
        _, rows = read_report(
            key, start_date=start.isoformat() if period else None,
            end_date=end.isoformat() if period else None,
        )
        payload, mime, ext = build_export(
            rows, list(spec.columns), fmt=extension,
            title=spec.title, warning=spec.warning,
        )
    except (PermissionError, DataReadError, ExportError, ValueError,
            RuntimeError, KeyError, TypeError) as exc:
        _LOG.warning("Export ERP indisponible (%s)", type(exc).__name__)
        st.error(
            "Aucun fichier créé : lecture non autorisée, incomplète, "
            "période invalide ou limite de taille dépassée."
        )
        return
    st.success(f"Export de {len(rows)} ligne(s) prêt : {spec.title}.")
    st.download_button(
        f"Télécharger {fmt}", data=payload, mime=mime,
        file_name=export_filename(spec.title, ext),
        key="ng_export_download",
    )
