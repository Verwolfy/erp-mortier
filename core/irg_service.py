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
    if db_client is None:
        from core.db_service import get_supabase_client
        db_client = get_supabase_client()
    try:
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
    if (not isinstance(query.data, list)
            or query.count is None
            or query.count != len(query.data)
            or len(query.data) > 1000):
        raise IRGNonDisponible("Lecture du barème IRG incomplète")
    return simuler_irg_mensuel(
        assiette, date_paie, categorie, query.data,
    )
