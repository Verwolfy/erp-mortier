"""Lecture contrôlée des paramètres de facturation depuis Supabase.

Lecture seule ; aucun repli vers un taux codé en dur si le registre est absent.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from core.fiscalite_facturation import FiscaliteNonDisponible, calculer_taxes_facture

_COLS = ("code,valeur,unite,date_effet,date_fin,statut_juridique,"
         "niveau_confiance,source,date_verification")


def fiscalite_facture_reglementee(
    montant_ht: str | int | Decimal,
    paiement_especes: bool,
    date_facture: date | str,
    *,
    db_client: Any = None,
) -> dict[str, Any]:
    """Lit toutes les versions applicables : refuse une réponse paginée tronquée."""
    if not isinstance(paiement_especes, bool):
        raise FiscaliteNonDisponible("Indicateur espèces invalide")
    if db_client is None:
        from core.db_service import get_supabase_client
        db_client = get_supabase_client()
    codes = ["TVA_VENTE_TAUX"]
    if paiement_especes:
        codes.extend(["TIMBRE_ESPECES_TAUX", "TIMBRE_ESPECES_PLAFOND"])
    try:
        response = (
            db_client.table("parametres_reglementaires")
            .select(_COLS, count="exact")
            .in_("code", codes)
            .order("code")
            .order("date_effet")
            .range(0, 999)
            .execute()
        )
    except Exception as exc:
        raise FiscaliteNonDisponible("Registre fiscal indisponible") from exc
    rows = response.data
    if (not isinstance(rows, list) or response.count is None
            or response.count != len(rows) or len(rows) > 1000):
        raise FiscaliteNonDisponible("Lecture réglementaire incomplète")
    return calculer_taxes_facture(montant_ht, paiement_especes, date_facture, rows)
