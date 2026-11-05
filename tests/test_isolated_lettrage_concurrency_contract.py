"""Contrat statique des scripts de double lettrage sur TEST uniquement."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1] / "sql" / "test_isole"
PREFIX = "20261105_concurrence_lettrage_"


def test_lettrage_parallel_contract_is_isolated():
    scripts = {
        part: (ROOT / f"{PREFIX}{part}.sql").read_text(encoding="utf-8")
        for part in ("PREP", "SESSION_A", "SESSION_B", "AUDIT", "NETTOYAGE")
    }
    for part in ("PREP", "SESSION_A", "SESSION_B", "NETTOYAGE"):
        assert "ffuhbmcfyexsbjwhryvj" in scripts[part]
        assert re.search(r"(?m)^BEGIN;$", scripts[part])
        assert re.search(r"(?m)^COMMIT;$", scripts[part])
    assert "RAISE EXCEPTION" in scripts["NETTOYAGE"]
    assert not re.search(r"(?im)^\s*(DROP|TRUNCATE|ALTER)\s+", scripts["NETTOYAGE"])
    for part, operation in (("SESSION_A", "IT26_LET_ALLOC_A"),
                            ("SESSION_B", "IT26_LET_ALLOC_B")):
        assert "SET LOCAL ROLE service_role;" in scripts[part]
        assert "erp_finance_transaction('ALLOCATE'" in scripts[part]
        assert operation in scripts[part]
        assert '"montant_applique":70' in scripts[part]
    assert "pg_sleep(5)" in scripts["SESSION_A"]
    assert not re.search(r"(?im)^\s*(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER)\s+", scripts["AUDIT"])
    assert "audit_ok" in scripts["AUDIT"]
    assert "allocations=1" in scripts["AUDIT"]
