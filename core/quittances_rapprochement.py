"""Rapprochement des règlements clients et des factures, sans écriture SQL.

Les quittances ne sont pas émises : seul un état interne, à partir des
règlements réellement enregistrés et de leurs lettrages, est préparé.
Une lecture tronquée, un paiement dupliqué, un surpaiement ou une incohérence
historique arrête tout le rapport au lieu d'afficher des soldes trompeurs.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from core.timbre_quittance import TimbreNonDisponible, calculer_timbre_quittance


class RapprochementIndisponible(ValueError):
    """Le lien entre règlement, facture et client ne peut être prouvé."""


def _texte(value: Any, champ: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 200:
        raise RapprochementIndisponible(f"{champ} manquant ou invalide")
    return value.strip()


def _montant(value: Any, champ: str, *, zero: bool = False) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise RapprochementIndisponible(f"{champ} non numérique")
    try:
        number = Decimal(str(value))
        if (not number.is_finite() or number < 0 or
                (number == 0 and not zero) or number >= Decimal("1e15") or
                number != number.quantize(Decimal("0.01"))):
            raise RapprochementIndisponible(f"{champ} hors limites ou précision invalide")
    except (InvalidOperation, ValueError) as exc:
        if isinstance(exc, RapprochementIndisponible):
            raise
        raise RapprochementIndisponible(f"{champ} incorrect") from exc
    return number


def _records(records: Sequence[Mapping[str, Any]], nom: str) -> list[Mapping[str, Any]]:
    if not isinstance(records, (list, tuple)) or len(records) > 10000:
        raise RapprochementIndisponible(f"{nom} manquant ou trop volumineux")
    if not all(isinstance(r, Mapping) for r in records):
        raise RapprochementIndisponible(f"{nom} contient une entrée non structurée")
    return list(records)


def rapprocher_reglements_clients(
    reglements: Sequence[Mapping[str, Any]],
    lettrages: Sequence[Mapping[str, Any]],
    factures: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Prépare des reçus *internes* ; aucune taxe, numéro légal ou paiement créé.

    Les trois jeux de données doivent couvrir tout l'historique concerné.
    Tous les règlements clients validés sont analysés, y compris ceux qui ne
    sont pas encore affectés à une facture. Un règlement affecté à plusieurs
    factures ne crée PAS plusieurs événements de timbre.
    """
    payments = _records(reglements, "Règlements")
    letters = _records(lettrages, "Lettrages")
    invoices = _records(factures, "Factures")
    by_payment: dict[str, dict[str, Any]] = {}
    by_invoice: dict[str, dict[str, Any]] = {}
    allocated: dict[str, Decimal] = defaultdict(Decimal)
    paid_invoices: dict[str, Decimal] = defaultdict(Decimal)
    allocation_ids: set[str] = set()
    links: dict[str, list[dict[str, str]]] = defaultdict(list)

    for row in payments:
        rid = _texte(row.get("reglement_id"), "Identifiant règlement")
        if rid in by_payment:
            raise RapprochementIndisponible("Identifiant de règlement répété")
        direction = row.get("type_flux")
        if direction not in ("ENCAISSEMENT", "DECAISSEMENT"):
            raise RapprochementIndisponible("Sens du règlement inconnu")
        if direction != "ENCAISSEMENT":
            continue
        if row.get("statut") != "VALIDE":
            # Un paiement annulé ne constitue pas une quittance.
            continue
        customer = _texte(row.get("partenaire_id"), "Client règlement")
        total = _montant(row.get("montant_total"), "Montant encaissé")
        assigned = _montant(row.get("montant_alloue"), "Montant affecté", zero=True)
        if assigned > total:
            raise RapprochementIndisponible("Règlement client sur-alloué")
        by_payment[rid] = {
            "reglement_id": rid, "client_id": customer,
            "date_reglement": _texte(row.get("date_reglement"), "Date règlement"),
            "mode_paiement": _texte(row.get("mode_paiement"), "Mode paiement"),
            "montant_encaisse": total, "montant_alloue": assigned,
        }
    for row in invoices:
        if row.get("type_facture") != "FactureClient" or row.get("statut") != "VALIDE":
            continue
        iid = _texte(row.get("facture_id"), "Identifiant facture")
        if iid in by_invoice:
            raise RapprochementIndisponible("Facture client dupliquée")
        total = _montant(row.get("montant_ttc"), "Total facture")
        paid = _montant(row.get("montant_paye"), "Montant payé facture", zero=True)
        if paid > total:
            raise RapprochementIndisponible("Facture historiquement surpayée")
        by_invoice[iid] = {
            "client_id": _texte(row.get("client_id"), "Client facture"),
            "montant_ttc": total, "montant_paye": paid,
        }

    for row in letters:
        lid = _texte(row.get("lettrage_id"), "Référence de lettrage")
        if lid in allocation_ids:
            raise RapprochementIndisponible("Lettrage dupliqué")
        allocation_ids.add(lid)
        rid = _texte(row.get("reglement_id"), "Règlement du lettrage")
        doc_type = row.get("type_document")
        # Les écritures de fournisseurs sont hors de cette synthèse.
        if doc_type == "FactureFournisseur":
            if rid in by_payment:
                raise RapprochementIndisponible("Règlement client affecté à un fournisseur")
            continue
        if doc_type != "FactureClient":
            raise RapprochementIndisponible("Type de document de lettrage inconnu")
        if rid not in by_payment:
            raise RapprochementIndisponible("Lettrage client sans encaissement validé")
        iid = _texte(row.get("document_id"), "Facture liée")
        if iid not in by_invoice:
            raise RapprochementIndisponible("Lettrage sur facture absente ou non validée")
        if by_invoice[iid]["client_id"] != by_payment[rid]["client_id"]:
            raise RapprochementIndisponible("Lettrage entre clients différents")
        amount = _montant(row.get("montant_applique"), "Montant du lettrage")
        allocated[rid] += amount
        paid_invoices[iid] += amount
        links[rid].append({"facture_id": iid, "montant_applique": format(amount, ".2f")})

    result = []
    for rid, p in by_payment.items():
        if allocated[rid] != p["montant_alloue"]:
            raise RapprochementIndisponible("Total lettré différent du règlement")
        result.append({
            "reglement_id": rid, "client_id": p["client_id"],
            "date_reglement": p["date_reglement"],
            "mode_paiement": p["mode_paiement"],
            "montant_encaisse": format(p["montant_encaisse"], ".2f"),
            "montant_alloue": format(p["montant_alloue"], ".2f"),
            "reste_a_affecter": format(p["montant_encaisse"]-p["montant_alloue"], ".2f"),
            "factures": links[rid],
            "statut": "ETAT_INTERNE_NON_QUITTANCE",
        })
    for iid, inv in by_invoice.items():
        if paid_invoices[iid] != inv["montant_paye"]:
            raise RapprochementIndisponible(
                "Montant payé facture incohérent avec tous les lettrages"
            )
    return {
        "reglements": sorted(result, key=lambda p: (p["date_reglement"], p["reglement_id"])),
        "nombre_reglements": len(result),
        "montant_encaisse_total": format(sum(
            (p["montant_encaisse"] for p in by_payment.values()), Decimal(0)
        ), ".2f"),
        "statut": "RAPPROCHEMENT_INTERNE_NON_CERTIFIE",
    }


def simuler_timbre_sur_encaissement(
    reglement: Mapping[str, Any],
    regles: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Utilise le règlement unique, non chaque facture lettrée.

    Les autres moyens (virement, chèque, etc.) nécessitent une qualification
    juridique : ne jamais assimiler leur exonération à celle de l'électronique.
    """
    if not isinstance(reglement, Mapping) or reglement.get("type_flux") != "ENCAISSEMENT" or reglement.get("statut") != "VALIDE":
        raise RapprochementIndisponible("Aucun encaissement client confirmé")
    try:
        return calculer_timbre_quittance(
            _montant(reglement.get("montant_total"), "Montant encaissé"),
            _texte(reglement.get("date_reglement"), "Date du règlement"),
            _texte(reglement.get("mode_paiement"), "Mode de paiement"),
            regles,
        )
    except TimbreNonDisponible as exc:
        raise RapprochementIndisponible("Simulation timbre non disponible ou non applicable") from exc
