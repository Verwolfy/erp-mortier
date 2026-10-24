"""010-A-02 — analyser un CSV d'audit SQL EXCLUSIVEMENT en local.

Usage : python -m scripts.verifier_audit_permissions_010a <rapport_csv>
Aucune connexion réseau. Ne reçoit jamais de clé/URL Supabase.
Codes retour : 0 (aucun blocage/alerte), 1 (révision requise),
               2 (blocage), 3 (rapport absent/invalide).
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

EXPECTED_RPC = frozenset({
    "erp_apply_stock_movement", "erp_close_manufacturing_order",
    "erp_start_manufacturing_order", "erp_create_purchase_order",
    "erp_receive_purchase_order", "erp_sale_transaction",
    "erp_finance_transaction", "erp_create_recipe",
    "erp_create_manufacturing_order", "erp_create_sales_order",
    "increment_compteur",
})
EXPECTED_TECH_TABLES = frozenset({
    "erp_stock_operations", "erp_stock_outbox", "erp_of_closures",
    "erp_of_outbox", "erp_purchase_operations", "erp_purchase_outbox",
    "erp_sales_operations", "erp_sales_outbox", "erp_finance_operations",
    "erp_finance_outbox", "erp_production_creations", "erp_sales_order_creations",
})
VALID_STATUSES = frozenset({"OK", "INFO", "A_VERIFIER", "BLOQUANT"})


class InvalidAuditReport(ValueError):
    """CSV incomplet ou ne provenant pas du rapport attendu."""


def read_report(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise InvalidAuditReport("Fichier CSV introuvable")
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            if reader.fieldnames is None or not {"categorie", "objet", "statut", "details"}.issubset(reader.fieldnames):
                raise InvalidAuditReport("Colonnes attendues : categorie, objet, statut, details")
            rows = [dict(row) for row in reader]
    except (UnicodeError, OSError, csv.Error) as exc:
        raise InvalidAuditReport("CSV illisible ou corrompu") from exc

    if not rows:
        raise InvalidAuditReport("Rapport vide")
    seen: set[tuple[str, str]] = set()
    for row in rows:
        if row["statut"] not in VALID_STATUSES or not row["categorie"] or not row["objet"]:
            raise InvalidAuditReport("Statut, catégorie ou objet invalide")
        key = (row["categorie"], row["objet"])
        if key in seen and row["categorie"] != "SURCHARGE_RPC":
            raise InvalidAuditReport(f"Ligne en doublon : {key!r}")
        seen.add(key)
    for categorie, expected in (("RPC_ATTENDUE", EXPECTED_RPC),
                                ("TABLE_TECHNIQUE", EXPECTED_TECH_TABLES),
                                ("SCHEMA_PUBLIC", frozenset({"public"}))):
        found = {r["objet"] for r in rows if r["categorie"] == categorie}
        if found != expected:
            raise InvalidAuditReport(
                f"Rapport incomplet ({categorie}) : manquants={sorted(expected - found)}, "
                f"inattendus={sorted(found - expected)}")
    return rows


def review_report(rows: list[dict[str, str]]) -> tuple[int, list[str]]:
    counts = Counter(row["statut"] for row in rows)
    messages = [
        f"Contrôles : {len(rows)} | BLOQUANT={counts['BLOQUANT']} | "
        f"A_VERIFIER={counts['A_VERIFIER']} | INFO={counts['INFO']} | OK={counts['OK']}"
    ]
    for row in rows:
        if row["statut"] in ("BLOQUANT", "A_VERIFIER"):
            messages.append(f"{row['statut']} — {row['categorie']} : {row['objet']}")
    if counts["BLOQUANT"]:
        return 2, messages
    if counts["A_VERIFIER"]:
        return 1, messages
    return 0, messages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rapport_csv", type=Path, help="CSV exporté du SQL Editor Supabase TEST")
    args = parser.parse_args()
    try:
        rows = read_report(args.rapport_csv)
        code, messages = review_report(rows)
    except InvalidAuditReport as exc:
        print(f"RAPPORT INVALIDE : {exc}")
        return 3
    for message in messages:
        print(message)
    print("Aucune permission n'a été modifiée. Vérification humaine indispensable.")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
