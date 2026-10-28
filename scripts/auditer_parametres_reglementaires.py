"""Audit non destructif des paramètres fiscaux figés dans le code ERP.

Un scan sans anomalie ne prouve pas la conformité réglementaire.
Exécuter --strict pour refuser la livraison en cas d'écart.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

PATTERNS = {
    "constante_tva_timbre": re.compile(
        r"\b(?:TAUX_TVA|TAUX_TIMBRE|MAX_TIMBRE)\s*=\s*(?:Decimal\s*\(\s*)?['\"]?\d+(?:\.\d+)?", re.I
    ),
    "calcul_tva_sql": re.compile(
        r"\bv_tax\s*:=\s*round\s*\(\s*v_net_ht\s*\*\s*\d+(?:\.\d+)?", re.I
    ),
    "timbre_sql": re.compile(
        r"\(\s*v_net_ht\s*\+\s*v_tax\s*\)\s*\*\s*\d+(?:\.\d+)?", re.I
    ),
    "taux_facture_sql": re.compile(
        r"\bv_net_ht\s*,\s*0\.\d+\s*,", re.I
    ),
}
SCAN_DIRS = ("core", "modules", "sql", "scripts", "config")
EXCLUDE = {"__pycache__", ".venv", ".git", "tests", "seeds", "docs"}

def audit(root: Path) -> list[dict[str, object]]:
    root = root.resolve()
    files = []
    for directory in SCAN_DIRS:
        folder = root / directory
        if folder.is_dir():
            files.extend(p for p in folder.rglob("*") if p.is_file() and p.suffix in (".py", ".sql"))
    if (root / "app.py").is_file():
        files.append(root / "app.py")
    findings: list[dict[str, object]] = []
    for path in sorted(set(files)):
        relative = path.relative_to(root)
        if any(part in EXCLUDE for part in relative.parts):
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            findings.append({"path": relative.as_posix(), "line": 0, "rule": "lecture_impossible"})
            continue
        for line_no, line in enumerate(source.splitlines(), 1):
            if line.lstrip().startswith(("#", "--")):
                continue
            for rule, expression in PATTERNS.items():
                if expression.search(line):
                    findings.append({"path": relative.as_posix(), "line": line_no, "rule": rule})
    return findings

def main() -> int:
    parser = argparse.ArgumentParser(description="Audit fiscal ERP sans modification")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--strict", action="store_true")
    options = parser.parse_args()
    findings = audit(options.root)
    print(json.dumps({"statut": "ECART" if findings else "AUCUN_ECART_DETECTE",
                      "nombre": len(findings), "ecarts": findings},
                     ensure_ascii=False, indent=2))
    return int(bool(findings) and options.strict)

if __name__ == "__main__":
    raise SystemExit(main())
