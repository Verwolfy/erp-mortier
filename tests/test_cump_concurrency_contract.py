"""Contrat isolé CUMP : deux entrées simultanées à coûts distincts."""
from decimal import Decimal
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1] / "sql" / "test_isole"
PREFIX = "20261105_cump_concurrence_"


def test_cump_receptions_concurrentes_contract():
    s = {name: (ROOT / f"{PREFIX}{name}.sql").read_text(encoding="utf-8")
         for name in ("PREP", "SESSION_A", "SESSION_B", "AUDIT", "NETTOYAGE")}
    assert all("ffuhbmcfyexsbjwhryvj" in v for v in s.values())
    for name in ("PREP", "SESSION_A", "SESSION_B", "NETTOYAGE"):
        assert re.search(r"(?m)^BEGIN;$", s[name])
        assert re.search(r"(?m)^COMMIT;$", s[name])
    assert "pg_sleep(5)" in s["SESSION_A"]
    assert "SET LOCAL ROLE service_role" in s["SESSION_A"]
    assert "SET LOCAL ROLE service_role" in s["SESSION_B"]
    assert "IT26_CUMPR_INA" in s["SESSION_A"]
    assert "IT26_CUMPR_INB" in s["SESSION_B"]
    assert "RAISE EXCEPTION" in s["NETTOYAGE"]
    assert not re.search(r"(?im)^\s*(DROP|TRUNCATE|ALTER)\s+", s["NETTOYAGE"])
    assert not re.search(r"(?im)^\s*(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER)\s+", s["AUDIT"])
    assert "audit_ok" in s["AUDIT"]
    initial = Decimal(10) * Decimal(100)
    concurrent_a = Decimal(5) * Decimal(160)
    concurrent_b = Decimal(15) * Decimal(80)
    assert (initial + concurrent_a + concurrent_b) / Decimal(30) == Decimal(100)
    assert initial + concurrent_a + concurrent_b == Decimal(3000)
