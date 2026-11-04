"""Panneau d'audit Finance/RH sans mutation, à intégrer dans Administration."""
import streamlit as st


def render_finance_rh_quality():
    st.divider()
    st.subheader("Cohérence Finance et RH")
    st.caption("Contrôles agrégés en lecture seule, sans émission ni écriture.")
    if st.button("Analyser la cohérence Finance", key="ng_quality_finance"):
        from modules.admin.finance_quality import audit_finance_autorise
        try:
            report = audit_finance_autorise()
        except (PermissionError, RuntimeError, ValueError, OSError):
            st.error("Lecture Finance refusée ou incomplète.")
        else:
            st.table(report)
            issues = sum(
                row["Liens manquants"] + row["Liens introuvables"] +
                row["Montants invalides"] + row["Montants négatifs"] +
                row["Allocations supérieures au règlement"]
                for row in report
            )
            st.warning(f"{issues} écarts potentiels à examiner.") if issues else st.success("Aucun écart structurel détecté.")

    if st.button("Analyser la cohérence RH", key="ng_quality_rh"):
        from modules.admin.rh_quality import audit_rh_autorise
        try:
            report = audit_rh_autorise()
        except (PermissionError, RuntimeError, ValueError, OSError):
            st.error("Lecture RH refusée ou incomplète.")
        else:
            st.table(report)
            issues = sum(
                row["Liens manquants"] + row["Liens introuvables"] +
                row["Dates invalides"] + row["Périodes inversées"] +
                row["Durées invalides"] for row in report
            )
            st.warning(f"{issues} écarts potentiels à examiner.") if issues else st.success("Aucun écart structurel détecté.")
            st.caption("Aucune information personnelle affichée.")
