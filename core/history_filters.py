"""Filtre de période facultatif pour les écrans d'historiques (sans cache).

La plage est vérifiée avant tout appel au service de lecture. L'absence
d'activation conserve le comportement 'tout l'historique'.
"""
from datetime import date, timedelta
import streamlit as st


def history_period_inputs(key: str) -> dict[str, str] | None:
    """Dates ISO destinées au filtre SQL du lecteur strict."""
    selected = st.checkbox("Limiter l'historique à une période", value=False,
                           key=f"{key}_period_enabled")
    if selected is not True:
        return {}
    today = date.today()
    first = st.date_input("Du", value=today - timedelta(days=30),
                          key=f"{key}_period_from")
    last = st.date_input("Au", value=today, key=f"{key}_period_to")
    if not isinstance(first, date) or not isinstance(last, date) or first > last:
        st.error("Période invalide : la date de début doit précéder la fin.")
        return None
    return {"start_date": first.isoformat(), "end_date": last.isoformat()}
