"""Recherche bornée et non mutante des référentiels ERP.

Le sélecteur est strictement limité aux référentiels explicitement approuvés.
On ne charge que les colonnes utiles à l'identification de l'article,
pas les coordonnées personnelles ou fiscales des tiers.
"""
from __future__ import annotations

from core import db_service as db

CATALOGS = {
    "clients": ("client_id", "nom", "categorie_client"),
    "fournisseurs": ("fournisseur_id", "nom", "categorie"),
    "produits": ("pf_id", "nom", "categorie_pf"),
    "matieres_premieres": ("mp_id", "nom", "categorie_mp"),
    "sku_conditionnement": ("sku_id", "format", "pf_id"),
}
PAGE_SIZE = 50
MAX_TOTAL = 100000


def search_referentiel(table: str, term: str, *, field: str | None = None,
                       page: int = 1) -> tuple[list[dict], int]:
    """Recherche ILIKE et pagination SQL, contrôle RBAC renouvelé à chaque appel.

    Caractères SQL LIKE spéciaux rejetés : la recherche porte sur le texte
    littéral et n'autorise pas l'élargissement arbitraire du périmètre.
    """
    if table not in CATALOGS:
        raise ValueError("Référentiel non pris en charge")
    identifier, name, category = CATALOGS[table]
    if field is None:
        field = name
    if field not in (identifier, name):
        raise ValueError("Champ de recherche non autorisé")
    if (not isinstance(term, str) or not 2 <= len(term.strip()) <= 80
            or any(char in term for char in ("%", "_", "\\", "\n", "\r", "\x00"))):
        raise ValueError("Saisir 2 à 80 caractères sans symboles de recherche SQL")
    if type(page) is not int or not 1 <= page <= 1000:
        raise ValueError("Numéro de page invalide")
    db._require_read_permission(table)
    columns = db._readable_columns(table)
    projection = (identifier, name, category, "actif")
    if not set(projection).issubset(columns):
        raise ValueError("Colonnes du référentiel non lisibles")
    offset = (page - 1) * PAGE_SIZE
    try:
        response = (db.get_supabase_client().table(table)
                    .select(",".join(projection), count="exact")
                    .ilike(field, "%" + term.strip() + "%")
                    .order(identifier)
                    .range(offset, offset + PAGE_SIZE - 1).execute())
        rows, count = response.data, response.count
        if (not isinstance(rows, list) or type(count) is not int
                or count < 0 or count > MAX_TOTAL
                or len(rows) != min(PAGE_SIZE, max(0, count - offset))):
            raise RuntimeError("Réponse de recherche incomplète")
        ids = [row.get(identifier) for row in rows if isinstance(row, dict)]
        if (len(ids) != len(rows) or len(set(ids)) != len(ids)
                or any(not isinstance(x, (str, int)) or isinstance(x, bool) or not str(x).strip()
                       for x in ids)):
            raise RuntimeError("Réponse de recherche incohérente")
        return rows, count
    except PermissionError:
        raise
    except Exception as exc:
        # Ni terme, ni réponse SQL, ni données personnelles dans l'UI.
        raise RuntimeError("Recherche momentanément indisponible") from None
