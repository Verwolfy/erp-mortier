"""Lecture contrôlée du barème IRG serveur, sans conserver le revenu saisi.

L'habilitation RH / Paie est vérifiée dans la vue, avant appel à ce service.
Les simulations ne sont jamais enregistrées ni émises comme bulletins.
"""
from __future__ import annotations

from typing import Any

from core.irg_salaires import IRGNonDisponible, simuler_irg_mensuel

_CHAMPS = ("code,type_regle,donnees,date_effet,date_fin,"
           "statut_juridique,niveau_confiance,source,date_verification")


def simuler_irg_depuis_supabase(
    assiette: str,
    date_paie: str,
    categorie: str,
    *,
    db_client: Any = None,
) -> dict[str, str]:
    """Refuse les réponses paginées ou tables absentes, sans repli tacite."""
    try:
        if db_client is None:
            from core.db_service import get_supabase_client
            db_client = get_supabase_client()
        query = (
            db_client.table("regles_reglementaires")
            .select(_CHAMPS, count="exact")
            .eq("code", "IRG_SALAIRES_MENSUEL")
            .order("date_effet")
            .range(0, 999)
            .execute()
        )
    except Exception as exc:
        raise IRGNonDisponible("Référentiel IRG inaccessible") from exc
    rows = getattr(query, "data", None)
    count = getattr(query, "count", None)
    if (not isinstance(rows, list)
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count != len(rows)
            or len(rows) > 1000
            or not all(isinstance(row, dict) for row in rows)):
        raise IRGNonDisponible("Lecture du barème IRG incomplète")
    return simuler_irg_mensuel(
        assiette, date_paie, categorie, rows,
    )
