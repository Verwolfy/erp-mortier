"""Audit EN LECTURE SEULE des stocks MP et PF sur Supabase.

Ancienne version: recalcul et réécriture automatique des quantités.
Cette version NE CONTIENT AUCUNE instruction INSERT/UPDATE/DELETE.
Les écarts nécessitent une analyse métier et une correction atomique dédiée.
Les lectures REST successives ne constituent PAS un instantané transactionnel.
"""
from __future__ import annotations

import os
import sys
# Compatible avec « python scripts/...py » et « python -m scripts... ».
from pathlib import Path
import sys
if __package__ in (None, ""):
    sys.path[:0] = [str(Path(__file__).resolve().parents[1])]

from core.environment_guard import (
    policy_from_environment, require_supabase_target,
)
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from datetime import datetime

PAGE_SIZE = 500
MAX_ROWS = 100_000
TOLERANCE = Decimal("0.01")


class StockAuditError(RuntimeError):
    """Audit non fiable: interdit toute conclusion quantitative."""


def _amount(value: object, context: str, *, positive: bool = False) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise StockAuditError(f"{context}: quantité manquante/invalide")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise StockAuditError(f"{context}: quantité non numérique") from exc
    if not result.is_finite() or (result <= 0 if positive else result < 0):
        raise StockAuditError(f"{context}: quantité hors bornes")
    return result


def _fetch_pages(client, table: str, id_col: str, selected_columns: tuple[str, ...]) -> list[dict]:
    """Pagination explicite et déterministe, sans troncature silencieuse."""
    rows: list[dict] = []
    while True:
        start = len(rows)
        if start > MAX_ROWS:
            raise StockAuditError(f"{table}: plus de {MAX_ROWS} lignes, audit interrompu")
        count = min(PAGE_SIZE, MAX_ROWS + 1 - start)
        response = (client.table(table)
                    .select(",".join(selected_columns))
                    .order(id_col)
                    .range(start, start + count - 1)
                    .execute())
        page = response.data
        if not isinstance(page, list) or any(not isinstance(row, dict) for row in page):
            raise StockAuditError(f"{table}: réponse Supabase invalide")
        if len(page) > count:
            raise StockAuditError(f"{table}: page plus grande que demandé")
        rows.extend(page)
        if len(page) < count:
            return rows


def _audit_type(client, *, item_type: str, movement_table: str,
                movement_id: str, stock_table: str, item_id: str) -> dict:
    moves = _fetch_pages(client, movement_table, movement_id,
                         (movement_id, item_id, "type_mouvement", "quantite"))
    stocks = _fetch_pages(client, stock_table, item_id, (item_id, "quantite_disponible"))
    theoretical: dict[str, Decimal] = defaultdict(Decimal)
    current: dict[str, Decimal] = {}

    for row in moves:
        key = row.get(item_id)
        kind = row.get("type_mouvement")
        if not isinstance(key, str) or not key.strip():
            raise StockAuditError(f"{movement_table}: identifiant {item_id} invalide")
        if kind not in ("ENTREE", "SORTIE"):
            raise StockAuditError(f"{movement_table}/{key}: mouvement non reconnu {kind!r}")
        quantity = _amount(row.get("quantite"), f"{movement_table}/{key}", positive=True)
        theoretical[key] += quantity if kind == "ENTREE" else -quantity

    for row in stocks:
        key = row.get(item_id)
        if not isinstance(key, str) or not key.strip() or key in current:
            raise StockAuditError(f"{stock_table}: identifiant absent/dupliqué")
        current[key] = _amount(row.get("quantite_disponible"), f"{stock_table}/{key}")

    differences: list[dict] = []
    for key in sorted(theoretical.keys() | current.keys()):
        expected = theoretical.get(key, Decimal(0))
        found = current.get(key, Decimal(0))
        delta = expected - found
        if abs(delta) > TOLERANCE or (key not in current and key in theoretical):
            differences.append({"id": key, "mouvements_net": str(expected),
                                "stock_actuel": str(found) if key in current else "ABSENT",
                                "ecart": str(delta)})
    return {"type": item_type, "mouvements": len(moves), "stocks": len(stocks),
            "ecarts": differences}


def auditer_et_corriger_stock_mp(supabase) -> dict:
    """Nom historique conservé. Audit MP uniquement; ne corrige JAMAIS."""
    return _audit_type(supabase, item_type="MP", movement_table="mouvements",
                       movement_id="mouvement_id", stock_table="stock_actuel", item_id="mp_id")


def auditer_et_corriger_stock_pf(supabase) -> dict:
    """Nom historique conservé. Audit PF uniquement; ne corrige JAMAIS."""
    return _audit_type(supabase, item_type="PF", movement_table="mouvements_pf",
                       movement_id="mouvement_pf_id", stock_table="stock_actuel_pf", item_id="sku_id")


def main() -> int:
    print(f"=== AUDIT LECTURE SEULE ({datetime.now():%Y-%m-%d %H:%M}) ===")
    url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY")
    if not url or not key:
        print("ERREUR: SUPABASE_URL et SUPABASE_KEY requis.", file=sys.stderr)
        return 2
    try:
        require_supabase_target(policy_from_environment(os.environ), url)
        from supabase import create_client
        client = create_client(url, key)
        reports = [auditer_et_corriger_stock_mp(client), auditer_et_corriger_stock_pf(client)]
        for report in reports:
            print(f"{report['type']}: {report['mouvements']} mouvements, "
                  f"{report['stocks']} stocks, {len(report['ecarts'])} écart(s)")
            for diff in report["ecarts"]:
                print(f"  ÉCART {diff['id']}: mouvements={diff['mouvements_net']}, "
                      f"stock={diff['stock_actuel']}, différence={diff['ecart']}")
        print("AUCUNE CORRECTION EXÉCUTÉE. Vérifier aussi les lots FIFO et les stocks d'ouverture.")
        return 1 if any(r["ecarts"] for r in reports) else 0
    except Exception as exc:
        print(f"AUDIT INCOMPLET: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
