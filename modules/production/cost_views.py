"""Écran du référentiel analytique industriel (aucune écriture de stock)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.production.cost_service import (
    BASES, add_pool, can_manage_costs, create_period, create_nature, document_pool,
    get_period_report, list_natures, list_periods, set_driver, validate_period,
)


def show_cost_reference(can_write: bool) -> None:
    st.subheader("Référentiel des coûts industriels analytiques")
    st.info("Les montants sont des coûts analytiques séparés du CUMP et du journal SCF. "
            "Aucune imputation aux stocks n'est réalisée depuis cet écran.")
    try:
        periods = list_periods()
        natures = list_natures()
    except Exception:
        st.error("Référentiel indisponible : vérifier la migration SQL 034 et les habilitations serveur.")
        return

    if not periods:
        st.info("Aucune période configurée.")
    else:
        st.dataframe(pd.DataFrame(periods), use_container_width=True, hide_index=True)
        selected = st.selectbox(
            "Période de référence",
            [p["period_id"] for p in periods],
            format_func=lambda k: next(
                (p["libelle"] + " — " + p["statut"] for p in periods if p["period_id"] == k), k))
        try:
            report = get_period_report(selected)
            audit = report.get("audit") or {}
            st.caption("Audit de complétude : " + ("CONFORME" if audit.get("audit_ok") else "À compléter"))
            st.json(audit)
            st.write("Charges de période")
            st.dataframe(pd.DataFrame(report["pools"]), use_container_width=True, hide_index=True)
            st.write("Rapprochement documentaire et plafond par ligne SCF")
            st.dataframe(pd.DataFrame(report["scf_reconciliation"]), use_container_width=True, hide_index=True)
            st.write("Clés et mesures par OF")
            st.dataframe(pd.DataFrame(report["drivers"]), use_container_width=True, hide_index=True)
            st.write("Synthèse des coûts analytiques par OF")
            st.dataframe(pd.DataFrame(report["summaries"]), use_container_width=True, hide_index=True)
            if report.get("validation_drift"):
                rows = report["validation_drift"]
                if any(r.get("derive_detectee") for r in rows):
                    st.error("Écart après validation : au moins un OF ou coût analytique a changé.")
                else:
                    st.success("Instantanés OF conformes à la validation analytique.")
                st.write("Instantané de validation et contrôle des dérives")
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            st.write("Détail des imputations calculées — aucune écriture comptable")
            st.dataframe(pd.DataFrame(report["allocations"]), use_container_width=True, hide_index=True)
        except Exception:
            st.error("Calcul analytique non disponible : contrôler le référentiel de la période.")
            return

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
    period_id = st.selectbox("Période brouillon à compléter",
                             [p["period_id"] for p in editable], key="cost_period_edit")
    with st.expander("Valider et figer la période"):
        st.warning("La validation est irréversible depuis cet écran : toutes les assiettes "
                   "doivent être renseignées et l'audit doit être conforme.")
        agree = st.checkbox("Je confirme les montants et les clés d'imputation",
                            key="cost_validate_ack")
        if st.button("Valider la période", disabled=not agree, key="cost_validate_button"):
            try:
                result = validate_period(period_id)
                st.success("Période validée. Montants et assiettes désormais verrouillés.")
                st.json(result)
            except Exception:
                st.error("Validation refusée : corriger les assiettes et exécuter l'audit.")
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
