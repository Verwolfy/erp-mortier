"""010-A-02 — validation locale des rapports d'audit exportés en CSV."""

import csv
from pathlib import Path

import pytest

from scripts.verifier_audit_permissions_010a import (
    EXPECTED_RPC, EXPECTED_TECH_TABLES, InvalidAuditReport,
    read_report, review_report,
)


def sample_rows():
    return [
        *({"categorie":"RPC_ATTENDUE", "objet":name, "statut":"OK", "details":"{}"}
          for name in sorted(EXPECTED_RPC)),
        *({"categorie":"TABLE_TECHNIQUE", "objet":name, "statut":"OK", "details":"{}"}
          for name in sorted(EXPECTED_TECH_TABLES)),
        {"categorie":"SCHEMA_PUBLIC", "objet":"public", "statut":"OK", "details":"{}"},
    ]


def write_csv(path: Path, rows, *, fields=("categorie", "objet", "statut", "details")):
    with path.open("w", newline="", encoding="utf-8-sig") as target:
        writer = csv.DictWriter(target, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def test_clean_report(tmp_path):
    csv_path = tmp_path / "audit.csv"
    write_csv(csv_path, sample_rows())
    rows = read_report(csv_path)
    code, message = review_report(rows)
    assert code == 0
    assert "BLOQUANT=0" in message[0]


def test_report_with_blocker(tmp_path):
    rows = sample_rows()
    rows[0]["statut"] = "BLOQUANT"
    path = tmp_path / "audit.csv"
    write_csv(path, rows)
    code, messages = review_report(read_report(path))
    assert code == 2
    assert any("BLOQUANT — RPC_ATTENDUE" in m for m in messages)


def test_warning_requires_review(tmp_path):
    rows = sample_rows()
    rows[2]["statut"] = "A_VERIFIER"
    rows.append({"categorie":"TABLE_METIER","objet":"produits","statut":"INFO","details":"{}"})
    path = tmp_path / "audit.csv"
    write_csv(path, rows)
    code, _ = review_report(read_report(path))
    assert code == 1


@pytest.mark.parametrize("index", [0, 3, 10])
def test_missing_critical_rows_is_invalid(tmp_path, index):
    rows = sample_rows()
    rows.pop(index)
    path = tmp_path / "audit.csv"
    write_csv(path, rows)
    with pytest.raises(InvalidAuditReport, match="incomplet"):
        read_report(path)


def test_missing_schema_is_invalid(tmp_path):
    rows = sample_rows()[:-1]
    path = tmp_path / "audit.csv"
    write_csv(path, rows)
    with pytest.raises(InvalidAuditReport, match="incomplet"):
        read_report(path)


def test_duplicate_is_invalid(tmp_path):
    rows = sample_rows()
    rows.append(rows[0].copy())
    path = tmp_path / "audit.csv"
    write_csv(path, rows)
    with pytest.raises(InvalidAuditReport, match="doublon"):
        read_report(path)


def test_invalid_column_or_status(tmp_path):
    path = tmp_path / "audit.csv"
    write_csv(path, sample_rows(), fields=("categorie", "objet", "statut"))
    with pytest.raises(InvalidAuditReport, match="Colonnes"):
        read_report(path)
    rows = sample_rows()
    rows[0]["statut"] = "CERTIFIE"
    write_csv(path, rows)
    with pytest.raises(InvalidAuditReport, match="invalide"):
        read_report(path)


def test_missing_file(tmp_path):
    with pytest.raises(InvalidAuditReport, match="introuvable"):
        read_report(tmp_path / "not-exist.csv")
