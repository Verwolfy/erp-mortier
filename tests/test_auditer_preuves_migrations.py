"""No-network tests: evidence filenames never certify executed SQL."""
import hashlib
import json
from pathlib import Path

import pytest

from scripts import auditer_preuves_migrations as audit


def snapshot(files=None):
    return {"captured_on": "2026-11-01", "migrations": [
        {"version": "20261027200803", "name": "erp_012_harden_principale_grants",
         "files": files if files is not None else [
             {"repo": "erp", "path": "sql/archive.sql", "category": "declared_archive"}]}
    ]}


def test_offline_hash_is_only_file_evidence(tmp_path):
    erp = tmp_path / "erp"
    (erp / "sql").mkdir(parents=True)
    data = b"-- candidate only\nSELECT 1;\n"
    (erp / "sql" / "archive.sql").write_bytes(data)
    report = audit.audit_snapshot(snapshot(), erp)
    ev = report[0]["evidence"][0]
    assert ev["sha256"] == hashlib.sha256(data).hexdigest()
    assert ev["status"] == "declared_archive_file_present_only"
    rendered = audit.render_markdown(report, "2026-11-01")
    assert "pas le SQL réellement exécuté" in rendered
    assert "public.schema_migrations" in rendered


def test_external_site_not_implied_missing(tmp_path):
    files = [{"repo": "site", "path": "sql/001.sql", "category": "proposal_not_executed"}]
    report = audit.audit_snapshot(snapshot(files), tmp_path)
    assert report[0]["evidence"][0]["status"] == "external_root_unavailable"
    assert report[0]["evidence"][0]["sha256"] is None
    site = tmp_path / "site"
    (site / "sql").mkdir(parents=True)
    (site / "sql" / "001.sql").write_text("SELECT 1;\n", encoding="utf-8")
    checked = audit.audit_snapshot(snapshot(files), tmp_path, site)
    assert checked[0]["evidence"][0]["status"] == "proposal_not_executed_file_present_only"


@pytest.mark.parametrize("invalid", [
    "/etc/passwd.sql",
    "sql/../../private.sql",
    "sql/../bad.sql",
    "sql/..",
    "sql/C:\\wrong.sql",
    "not_sql/file.sql",
    "sql/file.txt",
])
def test_path_escape_rejected(invalid):
    files = [{"repo": "erp", "path": invalid, "category": "candidate_unverified"}]
    with pytest.raises(audit.InvalidManifest):
        audit.validate_manifest(snapshot(files))


def test_unknown_category_rejected():
    files = [{"repo": "erp", "path": "sql/x.sql", "category": "definitely_applied"}]
    with pytest.raises(audit.InvalidManifest):
        audit.validate_manifest(snapshot(files))


def test_duplicate_version_and_file_rejected():
    one = snapshot()
    one["migrations"].append(one["migrations"][0])
    with pytest.raises(audit.InvalidManifest):
        audit.validate_manifest(one)
    two = snapshot()
    two["migrations"][0]["files"] *= 2
    with pytest.raises(audit.InvalidManifest):
        audit.validate_manifest(two)


def test_missing_file_is_detected_without_execution(tmp_path):
    report = audit.audit_snapshot(snapshot(), tmp_path)
    assert report[0]["evidence"][0]["status"] == "file_missing"
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(snapshot()), encoding="utf-8")
    assert audit.main(["--manifest", str(manifest), "--erp-root", str(tmp_path)]) == 1


def test_symlink_cannot_escape_repo(tmp_path):
    erp = tmp_path / "erp"
    (erp / "sql").mkdir(parents=True)
    outside = tmp_path / "outside.sql"
    outside.write_text("SELECT 1;\n", encoding="utf-8")
    (erp / "sql" / "archive.sql").symlink_to(outside)
    with pytest.raises(audit.InvalidManifest, match="Lien hors dépôt"):
        audit.audit_snapshot(snapshot(), erp)


def test_real_manifest_has_all_23_native_versions_without_claim_of_proof():
    manifest = json.loads((audit.ROOT / "docs/migration_evidence_20261101.json").read_text(encoding="utf-8"))
    migrations = audit.validate_manifest(manifest)
    assert len(migrations) == 23
    assert sum(x["name"].startswith("erp_") for x in migrations) == 21
    assert sum(x["name"].startswith("nextgen_site_") for x in migrations) == 2
    assert sum(any(e["category"] == "declared_archive" for e in x["files"]) for x in migrations) == 4
    assert all(not any(e.get("category") in ("applied", "proved") for e in x["files"]) for x in migrations)
    report = audit.audit_snapshot(manifest, audit.ROOT)
    assert not any(e["status"] == "file_missing" for row in report for e in row["evidence"])
    assert sum(e["status"] == "external_root_unavailable" for row in report
               for e in row["evidence"]) == 2


def test_no_secret_or_database_access_needed():
    source = (audit.ROOT / "scripts/auditer_preuves_migrations.py").read_text(encoding="utf-8")
    assert "import supabase" not in source
    assert "execute_sql(" not in source
    assert "subprocess" not in source
    assert "import requests" not in source
