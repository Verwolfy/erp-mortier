"""Performance CRM/Production : historiques consultés uniquement sur action."""
from pathlib import Path


def test_crm_historique_a_la_demande():
    content = Path("modules/crm/views.py").read_text(encoding="utf-8")
    assert 'if st.button("Afficher l\'historique CRM"' in content
    assert content.index('if st.button("Afficher l\'historique CRM"') < content.index("df_int = get_interactions()")
    assert "df_clients = get_clients_actifs() if can_write else pd.DataFrame()" in content


def test_production_historique_a_la_demande():
    content = Path("modules/production/views.py").read_text(encoding="utf-8")
    assert 'if st.button("Afficher l\'historique Production"' in content
    assert content.index('if st.button("Afficher l\'historique Production"') < content.index("consumed = get_consommations_of()")
    assert content.index('if st.button("Afficher l\'historique Production"') < content.index("controls = get_controles_qualite()")


def test_historiques_conservent_les_lecteurs_autorises():
    crm = Path("modules/crm/views.py").read_text(encoding="utf-8")
    prod = Path("modules/production/views.py").read_text(encoding="utf-8")
    assert 'with tab3, read_section("Historique CRM"):' in crm
    assert "access = _production_access()" in prod
    assert 'if access is None:' in prod


def test_production_referentiels_non_charges_en_lecture_seule():
    content = Path("modules/production/views.py").read_text(encoding="utf-8")
    assert "products = get_produits_actifs() if can_write else pd.DataFrame()" in content
    assert "materials = get_mp_actives() if can_write else pd.DataFrame()" in content
    assert "skus = get_skus_actifs() if can_write else pd.DataFrame()" in content
    # En lecture seule, le suivi des OF est accessible, sans leur clôture.
    assert 'orders = get_ordres_fabrication()' in content
