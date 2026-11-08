"""Lectures bornées pour les agrégats : une erreur n'est jamais une liste vide.

Aucun cache global, aucune écriture et mêmes gardes/projections que db_service.
Les pages ne constituent pas un snapshot transactionnel PostgreSQL : un changement
concurrent à cardinalité constante peut rester invisible malgré les contrôles.
"""
from contextlib import contextmanager
from datetime import date
import logging

from core import db_service as db
from core.query_diagnostics import measured_query_stage

_LOG = logging.getLogger(__name__)


class DataReadError(RuntimeError):
    """Données indisponibles, incomplètes ou incohérentes ; pas de résultat partiel."""


def fetch_data_strict(table_name, *, page_size=500, max_rows=10000,
                      date_column=None, start_date=None, end_date=None,
                      equal_column=None, equal_value=None,
                      only_primary_key=False):
    """SELECT paginé, trié par PK et contrôlé par count exact à chaque page.

    Une limite API plus petite que page_size est acceptée : on poursuit à partir
    du nombre effectivement reçu. Un total absent, variable ou excessif bloque
    le résultat, tout comme une page vide prématurée ou une PK répétée.

    Le mode only_primary_key lit uniquement la PK déclarée, en conservant
    EXACTEMENT les contrôles de droits, les bornes et la pagination.
    Ne doit pas être utilisé comme contournement du contrôle RBAC.
    """
    if (type(page_size) is not int or not 1 <= page_size <= 1000 or
            type(max_rows) is not int or not 1 <= max_rows <= 100000 or
            type(only_primary_key) is not bool):
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
    if equal_column is not None:
        if equal_column not in columns or type(equal_value) not in (str, int) or (isinstance(equal_value, str) and not equal_value.strip()):
            raise ValueError("Filtre de lecture invalide")
    elif equal_value is not None:
        raise ValueError("Colonne de filtre manquante")
    rows, seen, expected = [], set(), None
    try:
        while True:
            # Un client éphémère PAR PAGE sert aux deux requêtes :
            # vérification RBAC toujours fraîche, puis lecture métier.
            # Aucune réutilisation entre pages, rendus ou utilisateurs.
            with db.strict_read_page_client_scope():
                with measured_query_stage("check"):
                    db._require_read_permission(table_name)
                query = db.get_supabase_client().table(table_name).select(
                    key if only_primary_key else db._read_projection(table_name),
                    count="exact")
                if equal_column is not None:
                    query = query.eq(equal_column, equal_value)
                if date_column is not None:
                    query = query.gte(date_column, start_date).lte(date_column, end_date)
                with measured_query_stage("select"):
                    response = query.order(key).range(
                        len(rows), len(rows) + page_size - 1).execute()
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



def fetch_history_page_strict(table_name, *, page=1, page_size=50,
                              max_total=100000, date_column=None,
                              start_date=None, end_date=None):
    """Charge uniquement une page historique et annonce son total exact.

    Tri par date décroissante puis clé technique décroissante si demandé.\n    Sans date explicitement choisie : clé technique décroissante.\n    Pas un snapshot SQL :
    une mutation concurrente entre pages peut modifier la composition.
    Aucune page partielle n'est rendue comme résultat complet.
    """
    if (type(page) is not int or page < 1 or page > 1000 or
            type(page_size) is not int or not 1 <= page_size <= 100 or
            type(max_total) is not int or max_total < page_size):
        raise ValueError("Pagination historique invalide")
    columns = db._readable_columns(table_name)
    key = db._PRIMARY_KEY_OVERRIDES.get(
        table_name, db.SCHEMA_CONFIG[table_name]["cols"][0])
    if key not in columns:
        raise ValueError("Clé de lecture non autorisée")
    if date_column is not None and (not isinstance(date_column, str) or
                                    date_column not in columns or date_column == key):
        raise ValueError("Colonne chronologique non autorisée")
    if start_date is not None or end_date is not None:
        if date_column is None or not isinstance(start_date, str) or not isinstance(end_date, str):
            raise ValueError("Dates et colonne métier obligatoires")
        try:
            if (date.fromisoformat(start_date).isoformat() != start_date or
                    date.fromisoformat(end_date).isoformat() != end_date):
                raise ValueError("Dates ISO requises")
        except ValueError:
            raise ValueError("Dates ISO requises") from None
        if start_date > end_date:
            raise ValueError("Période historique inversée")
    start = (page - 1) * page_size
    if start >= max_total:
        raise ValueError("Page hors de la limite autorisée")
    try:
        with db.strict_read_page_client_scope():
            with measured_query_stage("check"):
                db._require_read_permission(table_name)
            query = db.get_supabase_client().table(table_name).select(
                db._read_projection(table_name), count="exact")
            if start_date is not None:
                # Ces filtres s'appliquent AVANT la pagination et au total exact.
                query = query.gte(date_column, start_date).lte(date_column, end_date)
            if date_column is not None:
                query = query.order(date_column, desc=True, nullsfirst=False)
            with measured_query_stage("select"):
                response = (query.order(key, desc=True)
                            .range(start, start + page_size - 1).execute())
        batch, count = response.data, response.count
        if (not isinstance(batch, list) or type(count) is not int or
                count < 0 or count > max_total or len(batch) > page_size):
            raise DataReadError("Pagination historique non vérifiable")
        expected = min(page_size, max(0, count - start))
        if len(batch) != expected:
            raise DataReadError("Page historique incomplète ou périmée")
        seen = set()
        for row in batch:
            if not isinstance(row, dict):
                raise DataReadError("Ligne historique invalide")
            identifier = row.get(key)
            if (type(identifier) not in (int, str) or
                    (isinstance(identifier, str) and not identifier.strip()) or
                    identifier in seen):
                raise DataReadError("Clé historique absente ou répétée")
            seen.add(identifier)
        return batch, count
    except (PermissionError, DataReadError):
        raise
    except Exception as exc:
        _LOG.warning("Page historique indisponible (%s)", type(exc).__name__)
        raise DataReadError("Page historique indisponible") from None


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
