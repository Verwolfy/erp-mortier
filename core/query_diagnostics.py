"""Mesures éphémères des lectures ERP : aucun contenu, identifiant ni secret.

Les compteurs sont isolés par ContextVar et ne survivent ni au rendu,
ni à un changement de session. Aucun journal ou export automatique.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from time import perf_counter
from typing import Iterator


_METRICS: ContextVar[dict[str, float] | None] = ContextVar(
    "sofiane_query_metrics", default=None
)
_FIELDS = ("checks", "check_ms", "selects", "select_ms",
           "clients", "client_ms", "cache_hits")


@contextmanager
def query_metrics_scope() -> Iterator[None]:
    """Isole les mesures au rendu actif ; les scopes imbriqués sont indépendants."""
    token = _METRICS.set({name: 0.0 for name in _FIELDS})
    try:
        yield
    finally:
        _METRICS.reset(token)


def query_metrics_snapshot() -> dict[str, float] | None:
    """Copie de chiffres agrégés, sans table, utilisateur, SQL, URL ni contenu."""
    current = _METRICS.get()
    return None if current is None else dict(current)


def record_cache_hit() -> None:
    current = _METRICS.get()
    if current is not None:
        current["cache_hits"] += 1


@contextmanager
def measured_query_stage(stage: str) -> Iterator[None]:
    """Compte les tentatives, y compris les refus et échecs, sans les journaliser.

    'check' inclut la vérification RBAC Supabase ; 'select' le transport +
    décodage d'une page ; 'client' seulement la création du client Python.
    Les durées se chevauchent : ne pas les additionner.
    """
    if stage not in ("check", "select", "client"):
        raise ValueError("Étape de mesure non reconnue")
    current = _METRICS.get()
    if current is None:
        yield
        return
    prefix = {"check": "checks", "select": "selects", "client": "clients"}[stage]
    duration_key = {"check": "check_ms", "select": "select_ms",
                    "client": "client_ms"}[stage]
    started = perf_counter()
    try:
        yield
    finally:
        current[prefix] += 1
        current[duration_key] += (perf_counter() - started) * 1000.0
