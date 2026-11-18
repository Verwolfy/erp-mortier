"""État des stocks MP/PF par période, lecture seule et calculs Decimal.

Les journaux ENTREE/SORTIE ne distinguent pas encore retours, pertes et casse.
Aucune requalification implicite d'une référence de mouvement n'est autorisée.
Les valeurs historiques utilisent exclusivement les coûts réellement enregistrés
sur les mouvements, jamais le PMP *actuel* appliqué au passé.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

_LIMIT = Decimal("1e15")
_MONEY = Decimal("0.01")


class StockStatementError(ValueError):
    """Impossible de garantir un état complet et cohérent."""


def _num(value: object, label: str, *, nullable: bool = False) -> Decimal | None:
    if value is None and nullable:
        return None
    if isinstance(value, bool):
        raise StockStatementError(f"{label} invalide")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise StockStatementError(f"{label} invalide") from exc
    if not number.is_finite() or number < 0 or number >= _LIMIT:
        raise StockStatementError(f"{label} invalide")
    return number


def _day(value: object) -> date:
    if not isinstance(value, str) or len(value) < 10:
        raise StockStatementError("Date de mouvement manquante")
    try:
        return date.fromisoformat(value[:10])
    except ValueError as exc:
        raise StockStatementError("Date de mouvement invalide") from exc


def _money(value: Decimal | None) -> str | None:
    return format(value.quantize(_MONEY), "f") if value is not None else None


def _quantity(value: Decimal) -> str:
    return format(value, "f")


def build_stock_statement(
    stocks: list[dict], movements: list[dict], *,
    item_type: str, start_date: str, end_date: str,
    labels: dict[str, tuple[str, str]] | None = None,
) -> list[dict]:
    """Reconstitue les soldes par article depuis le stock actuel et le journal entier.

    Il faut passer TOUT l'historique, sans pagination partielle. L'état est un
    rapport de gestion, non un inventaire signé ni une valorisation SCF.
    """
    if item_type not in {"MP", "PF"}:
        raise StockStatementError("Famille de stock invalide")
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except (TypeError, ValueError) as exc:
        raise StockStatementError("Période invalide") from exc
    if start > end or end > date.today():
        raise StockStatementError("Période inversée ou future")
    key = "mp_id" if item_type == "MP" else "sku_id"
    cost_key = "cmp_actuel" if item_type == "MP" else "cout_revient"
    mov_cost = "prix_entree" if item_type == "MP" else "cout_unitaire"
    mov_key = "mouvement_id" if item_type == "MP" else "mouvement_pf_id"
    if not isinstance(stocks, list) or not isinstance(movements, list):
        raise StockStatementError("Données de stock incomplètes")
    current: dict[str, tuple[Decimal, Decimal | None]] = {}
    for row in stocks:
        if not isinstance(row, dict) or not isinstance(row.get(key), str) or not row[key].strip():
            raise StockStatementError("Ligne de stock invalide")
        article = row[key]
        if article in current:
            raise StockStatementError("Article de stock dupliqué")
        current[article] = (
            _num(row.get("quantite_disponible"), "Stock actuel"),
            _num(row.get(cost_key), "PMP actuel", nullable=True),
        )
    journal: dict[str, list[tuple[date, str, Decimal, Decimal | None]]] = {}
    seen: set[str] = set()
    for row in movements:
        if not isinstance(row, dict):
            raise StockStatementError("Mouvement invalide")
        mid, article = row.get(mov_key), row.get(key)
        if not isinstance(mid, str) or not mid or mid in seen or not isinstance(article, str) or not article:
            raise StockStatementError("Mouvement sans clé unique ou article")
        seen.add(mid)
        if article not in current:
            raise StockStatementError("Mouvement sans stock actuel associé")
        direction = str(row.get("type_mouvement") or "").upper()
        if direction not in {"ENTREE", "SORTIE"}:
            raise StockStatementError("Type de mouvement non reconnu")
        qty = _num(row.get("quantite"), "Quantité mouvement")
        if qty <= 0:
            raise StockStatementError("Mouvement de quantité nulle")
        unit_cost = _num(row.get(mov_cost), "Coût mouvement", nullable=True)
        journal.setdefault(article, []).append((_day(row.get("date")), direction, qty, unit_cost))
    result = []
    for article, (qty_current, pmp) in sorted(current.items()):
        movements_article = journal.get(article, [])
        net_all = sum((qty if direction == "ENTREE" else -qty
                       for _, direction, qty, _ in movements_article), Decimal(0))
        baseline = qty_current - net_all
        if baseline < 0:
            raise StockStatementError(f"Historique quantitatif incompatible : {article}")
        entries = sum((qty for day, direction, qty, _ in movements_article
                       if start <= day <= end and direction == "ENTREE"), Decimal(0))
        exits = sum((qty for day, direction, qty, _ in movements_article
                     if start <= day <= end and direction == "SORTIE"), Decimal(0))
        prior = sum((qty if direction == "ENTREE" else -qty
                     for day, direction, qty, _ in movements_article if day < start), Decimal(0))
        after = sum((qty if direction == "ENTREE" else -qty
                     for day, direction, qty, _ in movements_article if day > end), Decimal(0))
        opening = baseline + prior
        closing = qty_current - after
        if opening < 0 or closing < 0 or opening + entries - exits != closing:
            raise StockStatementError(f"Chronologie de stock incohérente : {article}")
        before = [x for x in movements_article if x[0] < start]
        during = [x for x in movements_article if start <= x[0] <= end]
        to_end = before + during
        def valuation(lines: list[tuple[date, str, Decimal, Decimal | None]]) -> Decimal | None:
            if any(cost is None for _, _, _, cost in lines):
                return None
            return sum((qty * cost if direction == "ENTREE" else -(qty * cost)
                        for _, direction, qty, cost in lines), Decimal(0))
        entry_lines = [x for x in during if x[1] == "ENTREE"]
        exit_lines = [x for x in during if x[1] == "SORTIE"]
        valued = baseline == 0 and all(x[3] is not None for x in to_end)
        initial_value = valuation(before) if valued else None
        final_value = valuation(to_end) if valued else None
        # L'absence de coûts dans une partie du journal ne doit pas être masquée
        # par une valeur de stock reconstituée ou par un PMP courant.
        val_entry = valuation(entry_lines)
        # Les sorties sont présentées comme un montant positif dans le tableau ;
        # leur signe négatif n'est appliqué qu'au solde de valorisation.
        raw_exit = valuation(exit_lines)
        val_exit = -raw_exit if raw_exit is not None else None
        if final_value is not None and final_value < Decimal("-0.01"):
            raise StockStatementError(f"Valeur historique négative : {article}")
        name, unit = (labels or {}).get(article, (article, ""))
        result.append({
            "article": article, "designation": name, "unite": unit,
            "stock_initial": _quantity(opening),
            "entrees": _quantity(entries), "sorties": _quantity(exits),
            "retours_clients": None, "pertes": None,
            "stock_final": _quantity(closing),
            "pmp_actuel_dzd": _money(pmp),
            "valeur_stock_actuel_dzd": _money(qty_current * pmp) if pmp is not None else None,
            "valeur_initiale_dzd": _money(initial_value),
            "valeur_entrees_dzd": _money(val_entry),
            "valeur_sorties_dzd": _money(val_exit),
            "valeur_finale_historique_dzd": _money(final_value),
            "tracabilite": ("Complète (selon journal)" if baseline == 0
                            else "Stock antérieur sans mouvement traçable"),
            "valorisation": ("Historique valorisable" if valued
                              else "Historique non valorisable intégralement"),
        })
    return result


def current_stock_value(quantity: object, pmp: object) -> str | None:
    """Valorisation actuelle affichable, jamais estimée si PMP absent."""
    qty = _num(quantity, "Stock actuel")
    cost = _num(pmp, "PMP actuel", nullable=True)
    return _money(qty * cost) if cost is not None else None
