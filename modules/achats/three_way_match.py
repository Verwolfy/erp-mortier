"""ERP-063 — Rapprochement fournisseur BC / BR conforme / facture, lecture seule.

Un résultat concordant n'est JAMAIS une autorisation de paiement, une
validation fiscale, ni une preuve d'émission du BC. Tous les montants et
quantités proviennent de la base ; aucune donnée manquante n'est inventée.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation

from core.strict_reads import fetch_data_strict


class ThreeWayError(ValueError):
    """Pièces tronquées ou non vérifiables : aucun rapprochement présenté."""


def _id(value: object, label: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 128:
        raise ThreeWayError(f"{label} absent ou invalide")
    return value.strip()


def _number(value: object, label: str, *, required: bool = True) -> Decimal | None:
    if value is None:
        if not required:
            return None
        raise ThreeWayError(f"{label} absent")
    if isinstance(value, bool):
        raise ThreeWayError(f"{label} invalide")
    try:
        n = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ThreeWayError(f"{label} invalide") from exc
    if not n.is_finite() or n < 0 or n >= Decimal("1e15"):
        raise ThreeWayError(f"{label} hors limites")
    return n


def _sum_lines(rows: list[dict], *, key: str, quantity: str, price: str | None = None,
               total: str | None = None) -> dict[str, dict]:
    """Regroupe les lignes par matière, refuse des prix incohérents."""
    if not isinstance(rows, list) or not 1 <= len(rows) <= 200:
        raise ThreeWayError("Lignes absentes ou trop nombreuses")
    grouped: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ThreeWayError("Ligne invalide")
        item = _id(row.get(key), "Article")
        qty = _number(row.get(quantity), "Quantité")
        if qty <= 0:
            raise ThreeWayError("Quantité nulle")
        unit_price = _number(row.get(price), "Prix") if price else None
        amount = _number(row.get(total), "Montant HT") if total else None
        entry = grouped.setdefault(item, {
            "quantite": Decimal(0), "prix": unit_price, "montant": Decimal(0)
        })
        if price and entry["prix"] != unit_price:
            raise ThreeWayError("Prix contradictoires pour une même matière")
        entry["quantite"] += qty
        if price:
            if total and amount != qty * unit_price:
                raise ThreeWayError("Montant de ligne incompatible avec quantité × prix")
            entry["montant"] += amount if total else qty * unit_price
    return grouped


def reconcile_supplier_invoice(
    invoice: dict, purchase_order: dict, po_lines: list[dict],
    receipts: list[dict], receipt_lines: list[dict],
    invoice_lines: list[dict], sibling_invoices: list[tuple[dict, list[dict]]],
) -> dict:
    """Évaluation documentaire stricte ; jamais de statut PAYABLE."""
    if not isinstance(invoice, dict) or not isinstance(purchase_order, dict):
        raise ThreeWayError("En-têtes manquants")
    invoice_id = _id(invoice.get("facture_fournisseur_id"), "Facture")
    po_id = _id(purchase_order.get("commande_achat_id"), "Commande")
    supplier_id = _id(invoice.get("fournisseur_id"), "Fournisseur facture")
    _id(purchase_order.get("fournisseur_id"), "Fournisseur commande")
    blockers: list[str] = []
    remarks: list[str] = []

    if invoice.get("commande_achat_id") != po_id:
        blockers.append("Facture non rattachée à cette commande")
    if supplier_id != purchase_order["fournisseur_id"]:
        blockers.append("Fournisseur facture différent du fournisseur commande")
    if str(purchase_order.get("devise") or "").upper() != "DZD" or (
        _number(purchase_order.get("taux_change"), "Taux de change", required=False)
        != Decimal("1")
    ):
        blockers.append("Devise/taux non homologués : rapprochement DZD seul")
    if str(invoice.get("statut_paiement") or "").upper() not in ("NON_PAYEE", "PARTIELLE"):
        blockers.append("Statut facture non payable : brouillon, rejet ou état inconnu")

    po = _sum_lines(po_lines, key="mp_id", quantity="qte_totale",
                    price="prix_unitaire", total="total_devise")
    bill = _sum_lines(invoice_lines, key="mp_id_ou_service", quantity="quantite",
                      price="prix_unitaire", total="total_ht")
    if not isinstance(receipts, list) or len(receipts) > 200:
        raise ThreeWayError("Registre des réceptions incomplet")
    accepted_receipts = set()
    for br in receipts:
        if not isinstance(br, dict) or br.get("commande_achat_id") != po_id:
            raise ThreeWayError("Bon de réception non rattaché à la commande")
        key = _id(br.get("bon_reception_id"), "Bon de réception")
        if key in accepted_receipts:
            raise ThreeWayError("Bon de réception dupliqué")
        if str(br.get("controle_conformite") or "").strip().upper() in {"OUI", "CONFORME"}:
            accepted_receipts.add(key)
        else:
            blockers.append(f"Réception non conforme ou non qualifiée : {key}")
    received = defaultdict(Decimal)
    seen_br_lines: set[str] = set()
    if not isinstance(receipt_lines, list) or len(receipt_lines) > 10000:
        raise ThreeWayError("Lignes de réception incomplètes")
    for line in receipt_lines:
        if not isinstance(line, dict):
            raise ThreeWayError("Ligne de réception invalide")
        line_id = _id(line.get("ligne_br_id"), "Ligne de réception")
        if line_id in seen_br_lines:
            raise ThreeWayError("Ligne de réception en doublon")
        seen_br_lines.add(line_id)
        if line.get("bon_reception_id") not in {r["bon_reception_id"] for r in receipts}:
            raise ThreeWayError("Réception sans pièce justificative")
        if line["bon_reception_id"] in accepted_receipts:
            qty = _number(line.get("quantite_recue"), "Quantité réceptionnée")
            received[_id(line.get("mp_id"), "Matière reçue")] += qty

    if not isinstance(sibling_invoices, list) or not 1 <= len(sibling_invoices) <= 100:
        raise ThreeWayError("Factures de la commande non intégralement consultables")
    sibling_totals = defaultdict(Decimal)
    seen_invoices = set()
    for other, lines in sibling_invoices:
        if not isinstance(other, dict) or other.get("commande_achat_id") != po_id:
            raise ThreeWayError("Facture liée à une autre commande")
        other_id = _id(other.get("facture_fournisseur_id"), "Facture liée")
        if other_id in seen_invoices:
            raise ThreeWayError("Facture en double dans le registre")
        seen_invoices.add(other_id)
        if other.get("fournisseur_id") != purchase_order["fournisseur_id"]:
            blockers.append(f"Fournisseur incohérent sur une facture liée : {other_id}")
        # Pas de statut d'annulation métier fiable : compter TOUS les brouillons,
        # sans sous-estimer les quantités d'une facture dupliquée.
        for mp, entry in _sum_lines(lines, key="mp_id_ou_service",
                                    quantity="quantite", price="prix_unitaire",
                                    total="total_ht").items():
            sibling_totals[mp] += entry["quantite"]
    if invoice_id not in seen_invoices:
        raise ThreeWayError("Facture absente du registre cumulatif")

    report_rows = []
    for mp in sorted(set(po) | set(bill) | set(received) | set(sibling_totals)):
        ordered = po.get(mp, {}).get("quantite", Decimal(0))
        checked = received[mp]
        invoiced = bill.get(mp, {}).get("quantite", Decimal(0))
        cumulative = sibling_totals[mp]
        unit_price = po.get(mp, {}).get("prix")
        billed_price = bill.get(mp, {}).get("prix")
        errors = []
        if ordered == 0:
            errors.append("Matière non prévue au BC")
        if invoiced > checked:
            errors.append("Facturation supérieure aux réceptions conformes")
        if invoiced > ordered:
            errors.append("Facturation supérieure à la commande")
        if cumulative > checked or cumulative > ordered:
            errors.append("Surfacturation cumulée des factures associées")
        if billed_price is not None and unit_price != billed_price:
            errors.append("Prix facture différent du BC")
        if errors:
            blockers.extend(f"{mp} : {reason}" for reason in errors)
        report_rows.append({
            "mp_id": mp,
            "quantite_bc": str(ordered),
            "quantite_recue_conforme": str(checked),
            "quantite_facture": str(invoiced),
            "quantite_facturee_cumulee": str(cumulative),
            "prix_bc_dzd": str(unit_price) if unit_price is not None else None,
            "prix_facture_dzd": str(billed_price) if billed_price is not None else None,
            "constat": "; ".join(errors) if errors else "Concordant en quantité et prix",
        })

    ht = _number(invoice.get("montant_ht"), "HT facture", required=False)
    vat = _number(invoice.get("montant_tva"), "TVA facture", required=False)
    ttc = _number(invoice.get("montant_ttc"), "TTC facture", required=False)
    billed_ht = sum((r["montant"] for r in bill.values()), Decimal(0))
    if ht is None or ht != billed_ht:
        blockers.append("HT de l'en-tête absent ou différent des lignes enregistrées")
    if vat is None or ttc is None or ht is None:
        blockers.append("TVA ou TTC non documentés")
    elif ttc != ht + vat:
        blockers.append("HT + TVA différent du TTC enregistré")
    if not receipts:
        blockers.append("Aucun bon de réception rattaché")
    if not blockers:
        remarks.append("Concordance documentaire uniquement : visa, fiscalité et paiement non validés")
    return {
        "facture_fournisseur_id": invoice_id, "commande_achat_id": po_id,
        "verdict": "ECARTS_OU_PIECES_MANQUANTES" if blockers else "CONCORDANCE_DOCUMENTAIRE",
        "lignes": report_rows,
        "blocages": list(dict.fromkeys(blockers)),
        "observations": remarks,
        "autorise_paiement": False,
        "ecriture_stock": False,
        "certification_fiscale": False,
        "instantane_transactionnel": False,
    }


def load_supplier_invoice_match(invoice_id: str, *, reader=None) -> dict:
    """Lectures RBAC fraîches, strictes et bornées, sans jamais écrire en base."""
    invoice_id = _id(invoice_id, "Référence facture")
    if reader is None:
        reader = fetch_data_strict

    def load(table: str, column: str, value: str, limit: int = 200) -> list[dict]:
        rows = reader(table, equal_column=column, equal_value=value, max_rows=limit)
        if not isinstance(rows, list) or len(rows) > limit:
            raise ThreeWayError(f"Volume {table} non vérifiable")
        return rows

    def one(table: str, key: str, value: str) -> dict:
        result = load(table, key, value, 2)
        if len(result) != 1 or result[0].get(key) != value:
            raise ThreeWayError(f"Référence {table} ambiguë ou absente")
        return result[0]

    invoice = one("factures_fournisseurs", "facture_fournisseur_id", invoice_id)
    order_id = _id(invoice.get("commande_achat_id"), "Commande liée")
    po = one("commandes_achats", "commande_achat_id", order_id)
    po_lines = load("lignes_achats", "commande_achat_id", order_id)
    receipts = load("bons_reception", "commande_achat_id", order_id)
    receipt_lines = []
    for receipt in receipts:
        receipt_lines += load("lignes_bons_reception", "bon_reception_id",
                              _id(receipt.get("bon_reception_id"), "Réception"))
        if len(receipt_lines) > 10000:
            raise ThreeWayError("Trop de lignes de réception")
    inv_lines = load("lignes_factures_fournisseurs", "facture_fournisseur_id", invoice_id)
    sibling_headers = load("factures_fournisseurs", "commande_achat_id", order_id, 100)
    siblings = [
        (item, load("lignes_factures_fournisseurs", "facture_fournisseur_id",
                    _id(item.get("facture_fournisseur_id"), "Facture associée")))
        for item in sibling_headers
    ]
    return reconcile_supplier_invoice(invoice, po, po_lines, receipts,
                                      receipt_lines, inv_lines, siblings)
