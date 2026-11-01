"""Lectures bornées pour les agrégats : une erreur n'est jamais une liste vide.

Aucun cache global, aucune écriture et mêmes gardes/projections que db_service.
Les pages ne constituent pas un snapshot transactionnel PostgreSQL : un changement
concurrent à cardinalité constante peut rester invisible malgré les contrôles.
"""
from contextlib import contextmanager
from datetime import date
import logging

from core import db_service as db

_LOG = logging.getLogger(__name__)


class DataReadError(RuntimeError):
    """Données indisponibles, incomplètes ou incohérentes ; pas de résultat partiel."""


def fetch_data_strict(table_name, *, page_size=500, max_rows=10000,
                      date_column=None, start_date=None, end_date=None):
    """SELECT paginé, trié par PK et contrôlé par count exact à chaque page.

    Une limite API plus petite que page_size est acceptée : on poursuit à partir
    du nombre effectivement reçu. Un total absent, variable ou excessif bloque
    le résultat, tout comme une page vide prématurée ou une PK répétée.
    """
    if (type(page_size) is not int or not 1 <= page_size <= 1000 or
            type(max_rows) is not int or not 1 <= max_rows <= 100000):
        raise ValueError("Bornes de lecture invalides")
    columns = db._readable_columns(table_name)
    key = db._PRIMARY_KEY_OVERRIDES.get(table_name, db.SCHEMA_CONFIG[table_name]["cols"][0])
    if key not in columns:
        raise ValueError("Clé de pagination non lisible")
    if any(value is not None for value in (date_column, start_date, end_date)):
        if date_column not in columns:
            raise ValueError("Colonne de date non lisible")
        # Même convention que les appels existants : bornes YYYY-MM-DD incluses.
        for value in (start_date, end_date):
            if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
                raise ValueError("Date ISO attendue")
        if start_date > end_date:
            raise ValueError("Période inversée")
    rows, seen, expected = [], set(), None
    try:
        while True:
            # Revalider à chaque page ; aucune permission déduite du cache UI.
            db._require_read_permission(table_name)
            query = db.get_supabase_client().table(table_name).select(
                db._read_projection(table_name), count="exact")
            if date_column is not None:
                query = query.gte(date_column, start_date).lte(date_column, end_date)
            response = query.order(key).range(len(rows), len(rows) + page_size - 1).execute()
            batch, total = response.data, response.count
            if not isinstance(batch, list) or type(total) is not int or total < 0:
                raise DataReadError("Réponse de lecture non vérifiable")
            if total > max_rows:
                raise DataReadError("Volume au-delà de la limite de consultation")
            if expected is None:
                expected = total
            if total != expected or len(batch) > page_size or len(rows) + len(batch) > total:
                raise DataReadError("Lecture incohérente ou modifiée pendant la pagination")
            if not batch and len(rows) != total:
                raise DataReadError("Lecture interrompue avant le total annoncé")
            for row in batch:
                if not isinstance(row, dict):
                    raise DataReadError("Ligne de lecture invalide")
                identifier = row.get(key)
                if (type(identifier) not in (str, int) or
                        (isinstance(identifier, str) and not identifier.strip()) or
                        identifier in seen):
                    raise DataReadError("Clé de lecture absente ou dupliquée")
                seen.add(identifier)
            rows.extend(batch)
            if len(rows) == total:
                return rows
    except PermissionError:
        raise
    except DataReadError:
        raise
    except Exception as exc:
        # Ne pas exposer la réponse du serveur, ses en-têtes ou les valeurs lues.
        _LOG.warning("Lecture stricte indisponible (%s)", type(exc).__name__)
        raise DataReadError("Lecture indisponible ; aucun résultat complet") from None


def fetch_data_by_date_range_strict(table_name, date_column, start_date, end_date):
    return fetch_data_strict(table_name, date_column=date_column,
                             start_date=start_date, end_date=end_date)


@contextmanager
def read_section(label):
    """Isole une rubrique indisponible sans masquer les erreurs de programmation."""
    import streamlit as st
    try:
        yield
    except PermissionError:
        st.error(f"{label} : accès refusé. Vérifiez vos habilitations.")
    except DataReadError:
        st.error(f"{label} : données indisponibles ou incomplètes. "
                 "Aucun résultat complet ne peut être affiché ; réessayez la consultation.")
