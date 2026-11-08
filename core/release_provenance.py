"""Provenance d'exécution ERP : constat local, jamais une version inventée.

La version GitHub 'main' ou le dernier commit de CI ne prouvent PAS le code
réellement exécuté par Streamlit Cloud. On observe le checkout local lorsqu'il
est disponible ; une variable de déploiement reste seulement déclarative.
Aucun accès réseau, secret ou requête de base de données.
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Mapping

_SHA_RE = re.compile(r"[a-fA-F0-9]{40}\\Z")
_REPO_ROOT = Path(__file__).resolve().parents[1]


def _sha(value: object) -> str | None:
    if not isinstance(value, str) or not _SHA_RE.fullmatch(value):
        return None
    return value.lower()


@lru_cache(maxsize=1)
def _checkout_head() -> str | None:
    """Vérification locale sans réseau. Ne pas lire le Git du dossier parent."""
    if not (_REPO_ROOT / ".git").exists():
        return None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=_REPO_ROOT, timeout=2,
            check=False, capture_output=True, text=True,
        )
        if result.returncode == 0:
            return _sha(result.stdout.strip())
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


@dataclass(frozen=True)
class ReleaseEvidence:
    sha: str | None
    source: str
    expected: str | None
    status: str


def resolve_release(*, environ: Mapping[str, str],
                    checkout_sha: object = None) -> ReleaseEvidence:
    """Ne certifie jamais un SHA fourni uniquement par une variable d'environnement."""
    observed = _sha(checkout_sha)
    declared = _sha(environ.get("ERP_DEPLOY_SHA"))
    expected = _sha(environ.get("ERP_RELEASE_EXPECTED_SHA"))
    expected_raw = environ.get("ERP_RELEASE_EXPECTED_SHA")

    if expected_raw and expected is None:
        return ReleaseEvidence(observed or declared,
                               "checkout Git" if observed else
                               "déclaration de déploiement" if declared else "inconnu",
                               None, "SHA attendu invalide")
    if observed:
        status = ("CHECKOUT CONFORME" if expected == observed else "ÉCART DE VERSION"
                  if expected else "SHA attendu non fourni")
        return ReleaseEvidence(observed, "checkout Git local", expected, status)
    if declared:
        return ReleaseEvidence(declared, "déclaration non prouvée", expected,
                               "ÉCART DÉCLARÉ" if expected and expected != declared
                               else "NON VÉRIFIÉ")
    return ReleaseEvidence(None, "aucune preuve de checkout", expected,
                           "NON VÉRIFIABLE")


def release_caption(*, environ: Mapping[str, str] | None = None,
                    checkout_sha: object = None) -> str:
    """Libellé pour l'interface authentifiée. Aucune donnée secrète n'est exposée."""
    env = os.environ if environ is None else environ
    # checkout_sha=None laisse la recherche locale active. Les tests du calcul
    # peuvent passer une valeur explicite pour garantir le comportement attendu.
    checkout = _checkout_head() if checkout_sha is None else checkout_sha
    result = resolve_release(environ=env, checkout_sha=checkout)
    return (f"Version ERP : {result.sha or 'inconnue'} "
            f"· {result.source} · {result.status}")
