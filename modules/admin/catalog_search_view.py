"""Panneau de recherche serveur : aucun chargement global avant requête."""
import streamlit as st

from modules.admin.catalog_search import CATALOGS, search_referentiel


def render_catalog_search(table: str) -> None:
    if table not in CATALOGS:
        raise ValueError("Catalogue inconnu")
    identifier = CATALOGS[table][0]
    st.caption("Recherche rapide en lecture seule, 50 résultats maximum par page.")
    with st.form(f"ng_admin_search_{table}"):
        search = st.text_input("Rechercher une désignation ou un identifiant",
                               key=f"ng_admin_search_text_{table}")
        field = st.selectbox("Chercher dans", ["nom", identifier],
                             format_func=lambda v: "Nom" if v == "nom" else "Identifiant",
                             key=f"ng_admin_search_field_{table}")
        page = st.number_input("Page de résultats", min_value=1, max_value=1000,
                               step=1, value=1, key=f"ng_admin_search_page_{table}")
        submitted = st.form_submit_button("Rechercher")
    if not submitted:
        return
    try:
        rows, count = search_referentiel(table, search, field=field, page=int(page))
    except (PermissionError, ValueError, RuntimeError):
        st.error("Recherche indisponible : saisie, permission ou résultats à vérifier.")
        return
    st.caption(f"Page {int(page)} : {len(rows)} résultats sur {count}.")
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("Aucun résultat sur cette page.")
