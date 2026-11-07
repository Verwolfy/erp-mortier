"""Écran du référentiel analytique industriel (aucune écriture de stock)."""
from __future__ import annotations

import json
import logging
from decimal import Decimal, InvalidOperation

_LOG = logging.getLogger(__name__)

import pandas as pd
import streamlit as st
from modules.help.contextual import show_context_help, topic_help, field_help

from modules.production.cost_service import (
    BASES, add_pool, can_manage_costs, create_period, create_nature, document_pool,
    export_validated_period,
    get_period_report, get_validation_preflight, list_natures, list_periods,
    set_driver, validate_period,
)


COST_INTERFACE_MARKER = "SOF-ERP-COUTS-20261107-PRECHECK-02"


def show_cost_reference(can_write: bool) -> None:
    st.subheader("Référentiel des coûts industriels analytiques", help=topic_help("production.couts"))
    show_context_help(st, "production.couts")
    # Repère public de déploiement, sans jeton, URL privée ni identité.
    st.caption("Version interface Coûts industriels : " + COST_INTERFACE_MARKER)
    st.info("Les montants sont des coûts analytiques séparés du CUMP et du journal SCF. "
            "Aucune imputation aux stocks n'est réalisée depuis cet écran.")
    try:
        periods = list_periods()
        natures = list_natures()
    except PermissionError:
        st.error("Accès aux coûts industriels refusé : les droits de lecture Production ET Finance sont requis.")
        st.info("Demander à l'administrateur de vérifier le rôle du compte dans les deux modules.")
        return
    except Exception as exc:
        # Ne jamais exposer d'URL privée, de token ou de message d'API dans le navigateur.
        kind = type(exc).__name__
        _LOG.warning("Chargement du référentiel analytique impossible (%s)", kind)
        if kind == "StockClientConfigurationError":
            # Code fixe, jamais de valeurs de secret ou message d'exception fournisseur.
            reason = getattr(exc, "configuration_reason", "")
            guidance = {
                "missing": ("Clé serveur ou URL Supabase absente.",
                            "Renseigner supabase.url et supabase.stock_service_key "
                            "dans les secrets Streamlit du déploiement."),
                "empty_key": ("Clé serveur Stocks vide ou invalide.",
                              "Configurer une clé serveur service_role valide dans "
                              "supabase.stock_service_key (jamais côté navigateur)."),
                "url": ("URL Supabase invalide.",
                        "Vérifier le format HTTPS de supabase.url dans Streamlit Secrets."),
                "environment": ("Cible Supabase ou politique d'environnement refusée.",
                                "Contrôler erp_environment.name, production_supabase_url "
                                "et production_enabled sans désactiver la protection."),
                "client": ("Initialisation du client Supabase impossible.",
                           "Consulter les journaux Streamlit du serveur."),
            }
            headline, action = guidance.get(
                reason, ("Client serveur des coûts industriels non configuré.",
                         "Contrôler les secrets Streamlit côté serveur."))
            st.error(headline)
            st.info("Administrateur : " + action)
        else:
            st.error("Lecture des coûts industriels impossible : erreur de connexion ou de base.")
            st.info("Administrateur : consulter les journaux serveur pour identifier "
                    "le type d'erreur et vérifier la connexion Supabase.")
        return

    if not periods:
        st.info("Aucune période configurée.")
    else:
        st.dataframe(pd.DataFrame(periods), use_container_width=True, hide_index=True)
        selected = st.selectbox(
            "Période de référence",
            [p["period_id"] for p in periods],
            format_func=lambda k: next(
                (f"{p['libelle']} — {p['date_debut']} au {p['date_fin']} — {p['statut']}"
                 for p in periods if p["period_id"] == k), k))
        section_labels = {
            "pools": "Charges de période",
            "drivers": "Clés et mesures par OF",
            "allocations": "Détail des imputations calculées",
            "summaries": "Synthèse analytique par OF",
            "scf_reconciliation": "Rapprochement SCF",
            "validation_drift": "Instantané validé et dérives",
        }
        section = st.selectbox(
            "Section du rapport",
            list(section_labels),
            format_func=lambda code: section_labels[code],
            index=5 if next((p["statut"] for p in periods
                             if p["period_id"] == selected), "") == "VALIDE" else 0,
        )
        audit_requested = st.checkbox(
            "Calculer l'audit complet de la période (vérification coûteuse)",
            value=False, key="cost_report_full_audit",
        )
        try:
            # L'audit complet est calculé à la demande et jamais mis en cache.
            # La RPC de validation le recalculera obligatoirement.
            report = get_period_report(
                selected, sections=(section,), include_audit=audit_requested)
            if audit_requested:
                audit = report.get("audit") or {}
                # La RPC ne vérifie que l'équilibre ; 0 DZD = 0 DZD n'est
                # pas une période validable (contrôle distinct dans la RPC de validation).
                st.caption("Audit de répartition : " +
                           ("ÉQUILIBRÉ (ne vaut pas validation de la période)"
                            if audit.get("audit_ok") else "À compléter"))
                if audit.get("audit_ok") and audit.get("total_pools_dzd") is not None:
                    try:
                        empty_total = Decimal(str(audit["total_pools_dzd"])) == 0
                    except (InvalidOperation, ValueError, TypeError):
                        empty_total = False
                    if empty_total:
                        st.warning(
                            "Audit équilibré à 0 DZD : aucune charge à répartir. "
                            "Une période vide n'est pas validable ; charges, assiettes "
                            "et pièces SCF validées sont obligatoires.")
                st.json(audit)
            else:
                st.caption("Audit non calculé. Exécuter l'audit complet pour contrôler "
                           "la répartition avant toute validation.")
            st.caption("Section chargée : " + section_labels[section] +
                       ". Les autres tableaux ne sont pas téléchargés.")
            if section == "validation_drift":
                rows = report["validation_drift"]
                if rows:
                    if any(r.get("derive_detectee") for r in rows):
                        st.error("Écart après validation : au moins un OF ou coût analytique a changé.")
                    else:
                        st.success("Instantanés OF conformes à la validation analytique.")
                else:
                    st.info("Aucun instantané disponible pour cette période.")
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                if section == "pools" and not report[section]:
                    st.info("Aucune charge analytique sur cette période. "
                            "Les charges documentées et leurs assiettes sont requises "
                            "avant validation.")
                st.dataframe(pd.DataFrame(report[section]),
                             use_container_width=True, hide_index=True)
        except Exception:
            st.error("Calcul analytique non disponible : contrôler le référentiel de la période.")
            return

    if periods and next((p["statut"] for p in periods
                         if p["period_id"] == selected), "") == "VALIDE":
        st.caption("Export figé des coûts analytiques : distinct de la comptabilité légale SCF.")
        if st.button("Préparer l'export analytique validé", key="cost_export_prepare"):
            try:
                payload = export_validated_period(selected)
                st.download_button(
                    "Télécharger l'export JSON",
                    data=json.dumps(payload, ensure_ascii=False, indent=2),
                    file_name="couts_analytiques_valides.json",
                    mime="application/json",
                    key="cost_export_download",
                )
            except Exception:
                st.error("Export refusé : période non validée, preuves ou droits insuffisants.")

    if not can_write or not can_manage_costs():
        st.caption("Consultation uniquement. Écriture réservée aux profils habilités en Production et Finance.")
        return

    with st.expander("Nouvelle période analytique", expanded=False):
        with st.form("cost_create_period"):
            label = st.text_input("Libellé de période")
            start = st.date_input("Début de période")
            end = st.date_input("Fin de période")
            if st.form_submit_button("Créer la période"):
                try:
                    created = create_period(label, start.isoformat(), end.isoformat())
                    st.success(f"Période créée : {created}")
                except Exception:
                    st.error("Création refusée : vérifier dates, habilitations et disponibilité de la base.")

    editable = [p for p in periods if p["statut"] == "BROUILLON"]
    if not editable:
        return
    period_id = st.selectbox(
        "Période brouillon à compléter",
        [p["period_id"] for p in editable],
        format_func=lambda k: next(
            (f"{p['libelle']} — {p['date_debut']} au {p['date_fin']}"
             for p in editable if p["period_id"] == k), k),
        key="cost_period_edit")
    with st.expander("Précontrôle avant validation (lecture seule)"):
        st.caption(
            "Vérifie charges, assiettes, OF dans la période, pièces SCF validées "
            "et équilibre des imputations. Aucune comptabilisation ni validation.")
        if st.button("Vérifier les prérequis", key="cost_preflight_button"):
            try:
                check = get_validation_preflight(period_id)
                st.json(check["counts"])
                if check["ready"]:
                    st.success("Précontrôle satisfaisant ; la validation SQL reste décisive.")
                else:
                    st.warning("Période non validable en l'état :")
                    for issue in check["blockers"]:
                        st.caption("• " + issue)
                st.caption(check["avertissement"])
            except Exception:
                st.error("Précontrôle indisponible : ne pas valider cette période.")

    with st.expander("Valider et figer la période"):
        st.warning(
            "Validation irréversible : exige charges, OF terminés dans les dates, "
            "assiettes et pièces SCF validées. Le contrôle est relancé avant toute RPC.")
        agree = st.checkbox("Je confirme les montants et les clés d'imputation",
                            key="cost_validate_ack")
        if st.button("Valider la période", disabled=not agree, key="cost_validate_button"):
            try:
                check = get_validation_preflight(period_id)
                if check["ready"] is not True:
                    st.error("Validation bloquée : prérequis incomplets.")
                    for issue in check["blockers"]:
                        st.caption("• " + issue)
                else:
                    result = validate_period(period_id)
                    st.success("Période validée. Montants et assiettes désormais verrouillés.")
                    st.json(result)
            except Exception:
                st.error("Validation refusée : précontrôle ou validation SQL non confirmés.")
    with st.expander("Créer une nature de charge"):
        with st.form("cost_new_nature"):
            nature_code = st.text_input("Code nature (MAJUSCULES)")
            nature_label = st.text_input("Libellé de la nature")
            nature_desc = st.text_area("Description / périmètre")
            if st.form_submit_button("Créer la nature"):
                try:
                    create_nature(nature_code, nature_label, nature_desc)
                    st.success("Nature créée, sans montant automatique.")
                except Exception:
                    st.error("Nature refusée : code déjà utilisé, données invalides ou habilitation insuffisante.")
    with st.expander("Associer une pièce justificative à une charge"):
        st.caption("Seules les pièces SCF déjà VALIDÉES avec une ligne au débit "
                   "suffisante peuvent justifier une charge. Un brouillon SCF est refusé.")
        with st.form("cost_document_pool"):
            pool_ref = st.text_input("Identifiant du pool analytique")
            scf_piece = st.text_input("UUID de la pièce SCF validée")
            scf_line = st.number_input("Identifiant numérique de la ligne SCF au débit", min_value=1, step=1, value=1)
            explanation = st.text_area("Motif de rattachement à la fabrication (10 caractères minimum)")
            if st.form_submit_button("Documenter la charge"):
                try:
                    document_pool(period_id, pool_ref, scf_piece, int(scf_line), explanation)
                    st.success("Pièce SCF liée. Vérifier l’audit avant validation.")
                except Exception:
                    st.error("Documentation refusée : pièce SCF non validée, période ou droits incorrects.")
    if not natures:
        st.warning("Aucune nature active. Créer une nature avant de saisir une charge.")
    else:
        with st.expander("Ajouter une charge de période"):
            with st.form("cost_add_pool"):
                nature = st.selectbox("Nature de charge", [x["nature_code"] for x in natures],
                                      format_func=lambda code: next(
                                          (n["libelle"] for n in natures if n["nature_code"] == code), code))
                base = st.selectbox("Clé d'imputation", BASES)
                amount = st.text_input("Montant analytique (DZD)", value="0", help="Saisir jusqu’à 6 décimales, sans arrondi flottant.")
                reference = st.text_input("Justificatif / hypothèse (obligatoire)")
                if st.form_submit_button("Enregistrer la charge"):
                    try:
                        add_pool(period_id, nature, base, amount, reference)
                        st.success("Charge analytique enregistrée en simulation.")
                    except Exception:
                        st.error("Charge refusée : vérifier droits, période, montant et justificatif.")
    with st.expander("Renseigner une assiette pour un OF terminé"):
        st.caption("L'OF doit être terminé ET daté entre le début et la fin "
                   "de la période sélectionnée. Les OF d'octobre ne peuvent pas "
                   "être imputés à une période de novembre.")
        with st.form("cost_add_driver"):
            of_id = st.text_input("Identifiant de l'OF terminé")
            driver = st.selectbox("Clé mesurée", BASES)
            value = st.text_input("Valeur de la clé", value="0", help="Saisir jusqu’à 6 décimales, sans arrondi flottant.")
            reference = st.text_input("Source de la mesure / justificatif")
            if st.form_submit_button("Enregistrer l'assiette"):
                try:
                    set_driver(period_id, of_id, driver, value, reference)
                    st.success("Assiette enregistrée.")
                except Exception:
                    st.error("Assiette refusée : vérifier droits, OF terminé, dates et mesure.")
