"""Garanties non destructrices pour les historiques Stocks/Achats/Ventes."""
from pathlib import Path

MODULES = {
    "stocks": ("mouvements", "mouvements_pf"),
    "achats": ("commandes_achats", "bons_reception"),
    "ventes": ("factures",),
}


def test_historiques_sont_pagination_serveur():
    for module, tables in MODULES.items():
        src = Path(f"modules/{module}/views.py").read_text(encoding="utf-8")
        assert "fetch_history_page_strict" in src
        for table in tables:
            assert f'"{table}", page=int(' in src


def test_pages_ne_chargent_pas_avant_le_clic():
    stocks = Path("modules/stocks/views.py").read_text(encoding="utf-8")
    achats = Path("modules/achats/views.py").read_text(encoding="utf-8")
    ventes = Path("modules/ventes/views.py").read_text(encoding="utf-8")
    assert stocks.index('"Afficher les mouvements de stock"') < stocks.index('mp_rows, mp_total = fetch_history_page_strict(')
    assert achats.index('"Afficher l\'historique Achats"') < achats.index('rows_commandes, total_commandes = fetch_history_page_strict(')
    assert ventes.index('"Afficher les factures"') < ventes.index('rows, total = fetch_history_page_strict(')


def test_validation_des_factures_conserve_vue_complete():
    ventes = Path("modules/ventes/views.py").read_text(encoding="utf-8")
    assert 'invoices = get_factures() if can_write else pd.DataFrame()' in ventes
    assert '_workflow_tab(user_id, can_write, invoices)' in ventes
    assert 'eligible = factures[factures["statut"] == "BROUILLON"]' in ventes


def test_reception_achat_conserve_lecture_complete():
    achats = Path("modules/achats/views.py").read_text(encoding="utf-8")
    assert 'df_commandes = get_commandes()' in achats
    assert 'balances = _remaining_quantities' in achats


def test_filtrage_par_periode_est_facultatif_et_serveur():
    for module in MODULES:
        code = Path(f"modules/{module}/views.py").read_text(encoding="utf-8")
        assert "history_period_inputs" in code
        assert "period is not None and st.button(" in code
        assert "**period" in code
    filter_code = Path("core/history_filters.py").read_text(encoding="utf-8")
    assert 'selected is not True' in filter_code
    assert "first > last" in filter_code
