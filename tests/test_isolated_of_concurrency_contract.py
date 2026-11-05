"""Garde-fous des vraies sessions simultanées de clôture OF (TEST seulement)."""
from pathlib import Path
import re

DIR = Path(__file__).resolve().parents[1] / "sql" / "test_isole"
STEM = "20261105_concurrence_of_"


def test_close_of_concurrency_is_scoped_and_reversible():
    scripts = {
        stage: (DIR / f"{STEM}{stage}.sql").read_text(encoding="utf-8")
        for stage in ("PREP", "SESSION_A", "SESSION_B", "AUDIT", "NETTOYAGE")
    }
    assert all("ffuhbmcfyexsbjwhryvj" in script for script in scripts.values())
    for stage in ("PREP", "SESSION_A", "SESSION_B", "NETTOYAGE"):
        assert re.search(r"(?m)^BEGIN;$", scripts[stage])
        assert re.search(r"(?m)^COMMIT;$", scripts[stage])
    for stage in ("SESSION_A", "SESSION_B"):
        assert "SET LOCAL ROLE service_role;" in scripts[stage]
        assert "erp_close_manufacturing_order" in scripts[stage]
        assert "'IT26_OFR_OF'" in scripts[stage]
    assert "pg_sleep(5)" in scripts["SESSION_A"]
    assert "RAISE EXCEPTION" in scripts["NETTOYAGE"]
    assert "IT26_OFR_RAW" in scripts["NETTOYAGE"]
    assert "IT26_OFR_PACK" in scripts["NETTOYAGE"]
    assert "IT26_OFR_SKU" in scripts["NETTOYAGE"]
    assert "closures" in scripts["AUDIT"]
    assert "controles" in scripts["AUDIT"]
    assert "pf_produit" in scripts["AUDIT"]
    assert not re.search(r"(?im)^\s*(INSERT|UPDATE|DELETE|ALTER|DROP|TRUNCATE)\s+", scripts["AUDIT"])
    assert not re.search(r"(?im)^\s*(DROP|TRUNCATE|ALTER)\s+", scripts["NETTOYAGE"])
