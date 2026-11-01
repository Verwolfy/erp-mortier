"""Offline audit of declared migration evidence. Never executes SQL or connects to Supabase.

An archived or similarly named file is not proof of the exact SQL executed.
The input is a date-stamped metadata snapshot, NOT live database state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

CATEGORIES = frozenset({
    "declared_archive", "candidate_unverified", "thematic_draft",
    "proposal_not_executed",
})
ROOT = Path(__file__).resolve().parents[1]
VERSION = re.compile(r"^[0-9]{14}$")
NAME = re.compile(r"^[a-z0-9_]+$")


class InvalidManifest(ValueError):
    """Manifest cannot be trusted to describe candidate files."""


def validate_manifest(data: object) -> list[dict]:
    """Validate metadata and safe paths before any local file is inspected."""
    if not isinstance(data, dict) or not isinstance(data.get("migrations"), list):
        raise InvalidManifest("Liste des migrations absente")
    migrations = data["migrations"]
    if not migrations or len(migrations) > 250:
        raise InvalidManifest("Nombre de versions invalide")
    seen = set()
    for record in migrations:
        if not isinstance(record, dict):
            raise InvalidManifest("Version illisible")
        version, name, files = (record.get(key) for key in ("version", "name", "files"))
        if (not isinstance(version, str) or not VERSION.fullmatch(version)
                or not isinstance(name, str) or not NAME.fullmatch(name)
                or not isinstance(files, list) or len(files) > 30
                or version in seen):
            raise InvalidManifest("Version, nom ou candidats invalides")
        seen.add(version)
        per_version = set()
        for file in files:
            if not isinstance(file, dict):
                raise InvalidManifest("Source illisible")
            repo, rel, category = (file.get(key) for key in ("repo", "path", "category"))
            if (repo not in ("erp", "site") or category not in CATEGORIES
                    or not isinstance(rel, str) or not rel.endswith(".sql")):
                raise InvalidManifest("Source inconnue")
            path = PurePosixPath(rel)
            if (path.is_absolute() or len(path.parts) < 2 or path.parts[0] != "sql"
                    or any(part in ("..", ".") for part in rel.split("/"))
                    or chr(92) in rel or ":" in rel):
                raise InvalidManifest("Chemin SQL hors dépôt")
            if (repo, rel) in per_version:
                raise InvalidManifest("Source déclarée deux fois")
            per_version.add((repo, rel))
    return migrations


def audit_snapshot(manifest: dict, erp_root: Path, site_root: Path | None = None) -> list[dict]:
    """Hash only local candidate files; always label their SQL provenance unproven."""
    migrations = validate_manifest(manifest)
    roots = {"erp": erp_root.resolve(), "site": site_root.resolve() if site_root else None}
    report = []
    for item in migrations:
        evidence = []
        for source in item["files"]:
            label = source["category"]
            root = roots[source["repo"]]
            if root is None:
                evidence.append({**source, "status": "external_root_unavailable", "sha256": None})
                continue
            file_path = (root / source["path"]).resolve()
            # A symlink may not escape the provided repository root.
            if not file_path.is_relative_to(root):
                raise InvalidManifest("Lien hors dépôt")
            if not file_path.is_file():
                evidence.append({**source, "status": "file_missing", "sha256": None})
                continue
            if file_path.stat().st_size > 5_000_000:
                raise InvalidManifest("Fichier SQL excessif")
            digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
            evidence.append({**source, "status": f"{label}_file_present_only", "sha256": digest})
        report.append({"version": item["version"], "name": item["name"], "evidence": evidence})
    return report


def render_markdown(report: list[dict], captured_on: str) -> str:
    lines = [
        "# Revue hors ligne des fichiers de migrations",
        "",
        f"Instantané nominal Supabase du {captured_on}. Aucun accès réseau ni SQL exécuté.",
        "",
        "**Attention :** une empreinte SHA-256 prouve uniquement le contenu du fichier "
        "local consulté, pas le SQL réellement exécuté lors de la migration.",
        "",
        "| Version | Nom Supabase | Candidat local | Classement | SHA-256 local |",
        "|---|---|---|---|---|",
    ]
    for item in report:
        if not item["evidence"]:
            lines.append(f"| {item['version']} | {item['name']} | — | AUCUN FICHIER CANDIDAT | — |")
        for ev in item["evidence"]:
            path = f"{ev['repo']}:{ev['path']}"
            lines.append(f"| {item['version']} | {item['name']} | {path} | "
                         f"{ev['status']} | {ev['sha256'] or '—'} |")
    lines.extend(["", "La comparaison des SQL réellement exécutés exige une preuve indépendante.",
                  "Ne jamais renseigner public.schema_migrations ni rejouer un fichier sur cette seule base."])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit purement local, sans requête Supabase")
    parser.add_argument("--manifest", type=Path, default=ROOT / "docs/migration_evidence_20261101.json")
    parser.add_argument("--erp-root", type=Path, default=ROOT)
    parser.add_argument("--site-root", type=Path, default=None,
                        help="Facultatif : dossier du dépôt privé NextGen sur le poste")
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        report = audit_snapshot(manifest, args.erp_root, args.site_root)
        print(render_markdown(report, str(manifest.get("captured_on", "inconnu"))))
        missing = [ev for row in report for ev in row["evidence"] if ev["status"] == "file_missing"]
        return 1 if missing else 0
    except (InvalidManifest, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, f"Inventaire hors ligne invalide : {type(exc).__name__}\n")


if __name__ == "__main__":
    raise SystemExit(main())
