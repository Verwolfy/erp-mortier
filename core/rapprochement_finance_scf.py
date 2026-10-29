"""Audit de raccordement Finance → SCF, sans aucun poste comptable automatique.

Le circuit RPC Finance 006 produit deux écritures par règlement REGF-.
Ce module vérifie leur réalité et leur équilibre avant une éventuelle
transcription SCF. Aucun compte ou journal SCF n'est deviné.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence


class AuditTresorerieIndisponible(ValueError):
    """L'audit ne peut prouver l'exhaustivité et la cohérence financière."""


def _liste(value: Any, label: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, (list, tuple)) or len(value) > 10000:
        raise AuditTresorerieIndisponible(f"{label} incomplet ou volumineux")
    if not all(isinstance(item, Mapping) for item in value):
        raise AuditTresorerieIndisponible(f"{label} non structuré")
    return list(value)


def _ident(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 200:
        raise AuditTresorerieIndisponible(f"{field} invalide")
    return value.strip()


def _money(value: Any, field: str, *, allow_zero: bool = False) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise AuditTresorerieIndisponible(f"{field} non numérique")
    try:
        result = Decimal(str(value))
        if (
            not result.is_finite() or result < 0 or
            (not allow_zero and result == 0) or result >= Decimal("1e15") or
            result != result.quantize(Decimal("0.01"))
        ):
            raise AuditTresorerieIndisponible(f"{field} hors limites")
    except (ValueError, InvalidOperation) as exc:
        raise AuditTresorerieIndisponible(f"{field} incorrect") from exc
    return result


def _date_iso(value: Any) -> str:
    if not isinstance(value, str):
        raise AuditTresorerieIndisponible("Date absente")
    try:
        jour = date.fromisoformat(value)
    except ValueError as exc:
        raise AuditTresorerieIndisponible("Date financière invalide") from exc
    if jour.isoformat() != value:
        raise AuditTresorerieIndisponible("Date non ISO")
    return value


def auditer_reglements_vers_scf(
    reglements: Sequence[Mapping[str, Any]],
    ecritures: Sequence[Mapping[str, Any]],
    comptes: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Vérifie le journal Finance lié aux paiements RPC, sans le poster en SCF.

    Les règlements historiques sans préfixe REGF- sont exclus et dénombrés,
    jamais déclarés compatibles SCF sans preuve d'origine.
    """
    reglements = _liste(reglements, "Règlements")
    ecritures = _liste(ecritures, "Écritures")
    comptes = _liste(comptes, "Comptes")

    by_account = {}
    for row in comptes:
        cid = _ident(row.get("compte_id"), "Identifiant compte")
        if cid in by_account:
            raise AuditTresorerieIndisponible("Compte bancaire ou tiers dupliqué")
        by_account[cid] = row

    payments: dict[str, Mapping[str, Any]] = {}
    legacy = 0
    for row in reglements:
        rid = _ident(row.get("reglement_id"), "Identifiant règlement")
        if not rid.startswith("REGF-"):
            legacy += 1
            continue
        if rid in payments:
            raise AuditTresorerieIndisponible("Règlement RPC dupliqué")
        if row.get("statut") != "VALIDE":
            raise AuditTresorerieIndisponible("Règlement RPC non validé")
        if row.get("type_flux") not in ("ENCAISSEMENT", "DECAISSEMENT"):
            raise AuditTresorerieIndisponible("Sens du règlement inconnu")
        _date_iso(row.get("date_reglement"))
        _ident(row.get("partenaire_id"), "Partenaire")
        _ident(row.get("compte_id"), "Compte de trésorerie")
        amount = _money(row.get("montant_total"), "Montant règlement")
        applied = _money(row.get("montant_alloue"), "Montant alloué", allow_zero=True)
        if applied > amount:
            raise AuditTresorerieIndisponible("Montant règlement dépassé")
        payments[rid] = row

    entries: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_entries: set[str] = set()
    for row in ecritures:
        # Le journal peut contenir des écritures de stocks, régularisations ou
        # importations historiques non issues de la RPC Finance 006.
        source = row.get("document_source_id")
        if not isinstance(source, str) or not source.startswith("REGF-"):
            continue
        eid = _ident(row.get("ecriture_id"), "Référence écriture")
        if eid in seen_entries:
            raise AuditTresorerieIndisponible("Écriture de trésorerie dupliquée")
        seen_entries.add(eid)
        if source not in payments:
            raise AuditTresorerieIndisponible("Écriture orpheline d'un règlement RPC")
        entries[source].append(dict(row))

    results = []
    total_in = Decimal("0")
    total_out = Decimal("0")
    for rid, payment in sorted(payments.items()):
        pair = entries.get(rid, [])
        if len(pair) != 2:
            raise AuditTresorerieIndisponible("Journal de paiement à deux lignes incomplet")
        amount = _money(payment["montant_total"], "Montant RPC")
        date_payment = payment["date_reglement"]
        direction = payment["type_flux"]
        cash_account = _ident(payment["compte_id"], "Compte du règlement")
        seen_accounts = set()
        total_debit = Decimal("0")
        total_credit = Decimal("0")
        cash_found = False
        lines = []

        for entry in pair:
            account_id = _ident(entry.get("compte_id"), "Compte écriture")
            if account_id in seen_accounts:
                raise AuditTresorerieIndisponible("Une écriture répète le même compte")
            seen_accounts.add(account_id)
            account = by_account.get(account_id)
            if not isinstance(account, Mapping) or str(account.get("statut")).upper() != "OUI":
                raise AuditTresorerieIndisponible("Compte de règlement absent ou inactif")
            entry_date = _date_iso(entry.get("date_ecriture"))
            if entry_date != date_payment:
                raise AuditTresorerieIndisponible("Date d'écriture différente du règlement")
            debit = _money(entry.get("debit"), "Débit", allow_zero=True)
            credit = _money(entry.get("credit"), "Crédit", allow_zero=True)
            if (debit > 0) == (credit > 0):
                raise AuditTresorerieIndisponible("Débit et crédit non exclusifs")
            total_debit += debit
            total_credit += credit
            kind = str(account.get("type_compte") or "").strip().casefold()
            is_cash = account_id == cash_account
            if is_cash:
                cash_found = True
                if kind not in ("banque", "caisse") or (
                    direction == "ENCAISSEMENT" and debit != amount
                ) or (direction == "DECAISSEMENT" and credit != amount):
                    raise AuditTresorerieIndisponible("Sens ou type de compte trésorerie incorrect")
            elif (
                direction == "ENCAISSEMENT" and kind not in ("tiers client", "client", "clients")
            ) or (
                direction == "DECAISSEMENT" and kind not in ("tiers fournisseur", "fournisseur", "fournisseurs")
            ):
                raise AuditTresorerieIndisponible("Type de contrepartie incorrect")
            lines.append({
                "compte_finance": account_id,
                "numero_compte_saisi": account.get("numero_compte"),
                "debit": format(debit, ".2f"),
                "credit": format(credit, ".2f"),
            })
        if not cash_found or total_debit != amount or total_credit != amount:
            raise AuditTresorerieIndisponible("Écriture sans trésorerie ou déséquilibrée")
        if direction == "ENCAISSEMENT":
            total_in += amount
        else:
            total_out += amount
        results.append({
            "reglement_id": rid,
            "date_ecriture": date_payment,
            "sens": direction,
            "montant": format(amount, ".2f"),
            "total_debit": format(total_debit, ".2f"),
            "total_credit": format(total_credit, ".2f"),
            "lignes": lines,
            "statut": "VERIFIE_FINANCE_NON_COMPTABILISE_SCF",
        })

    return {
        "reglements_rpc_valides": len(results),
        "reglements_historiques_hors_controle": legacy,
        "montant_encaisse": format(total_in, ".2f"),
        "montant_decaisse": format(total_out, ".2f"),
        "ecritures": results,
        "statut": "AUDIT_FINANCE_NON_CERTIFIE_SCF",
    }
