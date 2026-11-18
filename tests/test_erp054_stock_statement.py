"""ERP-054 — États de stock et PMP, sans accès à Supabase."""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from modules.stocks.stock_statement import (
    StockStatementError, build_stock_statement, current_stock_value,
)


def _fixture(kind="MP"):
    today = date.today()
    before, entry, exit_day = ((today - timedelta(days=3)).isoformat(),
                               (today - timedelta(days=1)).isoformat(),
                               today.isoformat())
    key = "mp_id" if kind == "MP" else "sku_id"
    mk = "mouvement_id" if kind == "MP" else "mouvement_pf_id"
    price = "prix_entree" if kind == "MP" else "cout_unitaire"
    cost = "cmp_actuel" if kind == "MP" else "cout_revient"
    stock = [{key: "ITEM-1", "quantite_disponible": "18", cost: "150"}]
    moves = [
        {mk: "M-1", key: "ITEM-1", "date": before + " 08:00:00",
         "type_mouvement": "ENTREE", "quantite": "10", price: "100"},
        {mk: "M-2", key: "ITEM-1", "date": entry + " 08:00:00",
         "type_mouvement": "ENTREE", "quantite": "10", price: "200"},
        {mk: "M-3", key: "ITEM-1", "date": exit_day + " 08:00:00",
         "type_mouvement": "SORTIE", "quantite": "2", price: "150"},
    ]
    return stock, moves, entry, exit_day


@pytest.mark.parametrize("kind", ["MP", "PF"])
def test_period_quantities_and_historic_valuation(kind):
    stock, moves, start, end = _fixture(kind)
    row = build_stock_statement(stock, moves, item_type=kind,
                                start_date=start, end_date=end)[0]
    assert row["stock_initial"] == "10"
    assert row["entrees"] == "10"
    assert row["sorties"] == "2"
    assert row["stock_final"] == "18"
    assert row["valeur_initiale_dzd"] == "1000.00"
    assert row["valeur_entrees_dzd"] == "2000.00"
    assert row["valeur_sorties_dzd"] == "300.00"
    assert row["valeur_finale_historique_dzd"] == "2700.00"
    assert row["pmp_actuel_dzd"] == "150.00"
    assert row["valeur_stock_actuel_dzd"] == "2700.00"
    assert row["retours_clients"] is None
    assert row["pertes"] is None
    assert row["tracabilite"] == "Complète (selon journal)"


def test_missing_historic_price_never_uses_current_pmp():
    stock, moves, start, end = _fixture()
    moves[0]["prix_entree"] = None
    row = build_stock_statement(stock, moves, item_type="MP",
                                start_date=start, end_date=end)[0]
    assert row["valeur_initiale_dzd"] is None
    assert row["valeur_finale_historique_dzd"] is None
    assert row["valeur_stock_actuel_dzd"] == "2700.00"
    assert row["valorisation"] == "Historique non valorisable intégralement"


def test_untracked_initial_stock_does_not_fabricate_valuation():
    stock, moves, start, end = _fixture()
    stock[0]["quantite_disponible"] = "20"
    row = build_stock_statement(stock, moves, item_type="MP",
                                start_date=start, end_date=end)[0]
    assert row["stock_initial"] == "12"
    assert row["stock_final"] == "20"
    assert row["valeur_initiale_dzd"] is None
    assert row["valeur_finale_historique_dzd"] is None
    assert row["tracabilite"] == "Stock antérieur sans mouvement traçable"


@pytest.mark.parametrize("damage", ["negative_baseline", "duplicate", "unknown_type", "unknown_item"])
def test_invalid_history_fails_closed(damage):
    stock, moves, start, end = _fixture()
    if damage == "negative_baseline":
        stock[0]["quantite_disponible"] = "1"
    elif damage == "duplicate":
        moves[1]["mouvement_id"] = "M-1"
    elif damage == "unknown_type":
        moves[1]["type_mouvement"] = "RETOUR_CLIENT"
    elif damage == "unknown_item":
        moves[1]["mp_id"] = "ABSENT"
    with pytest.raises(StockStatementError):
        build_stock_statement(stock, moves, item_type="MP",
                              start_date=start, end_date=end)


def test_historical_valuation_before_future_movements():
    stock, moves, _, end = _fixture()
    start = (date.today() - timedelta(days=3)).isoformat()
    prior_end = (date.today() - timedelta(days=2)).isoformat()
    row = build_stock_statement(stock, moves, item_type="MP",
                                start_date=start, end_date=prior_end)[0]
    assert row["stock_final"] == "10"
    assert row["valeur_finale_historique_dzd"] == "1000.00"


def test_zero_stock_and_missing_cost_do_not_invent_price():
    today = date.today().isoformat()
    row = build_stock_statement(
        [{"mp_id": "M", "quantite_disponible": "0", "cmp_actuel": None}], [],
        item_type="MP", start_date=today, end_date=today,
    )[0]
    assert row["pmp_actuel_dzd"] is None
    assert row["valeur_stock_actuel_dzd"] is None
    assert row["stock_final"] == "0"
    assert current_stock_value("0", None) is None


def test_weighted_average_current_value():
    assert current_stock_value("18", "150") == "2700.00"
    assert current_stock_value("0.003", "10") == "0.03"
    for value in ("NaN", "-1", "Infinity"):
        with pytest.raises(StockStatementError):
            current_stock_value("10", value)
