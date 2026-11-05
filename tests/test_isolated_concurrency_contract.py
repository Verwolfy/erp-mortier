"""Garde-fous des deux scénarios de concurrence sur le projet TEST.

Ces tests lisent les scripts SQL ; ils ne se connectent jamais à Supabase.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1] / "sql" / "test_isole"
TEST_REF = "ffuhbmcfyexsbjwhryvj"
STEMS = ("commande", "finance")


def test_concurrency_scenarios_are_scoped_to_test_and_have_cleanup():
    for stem in STEMS:
        paths = {
            phase: ROOT / f"20261105_concurrence_{stem}_{phase}.sql"
            for phase in ("PREP_TEST", "SESSION_A", "SESSION_B", "AUDIT", "NETTOYAGE_TEST")
        }
        scripts = {phase: p.read_text(encoding="utf-8")
                   for phase, p in paths.items()}
        assert all(TEST_REF in script for script in scripts.values())
        assert "BEGIN;" in scripts["PREP_TEST"]
        assert "COMMIT;" in scripts["PREP_TEST"]
        assert "BEGIN;" in scripts["NETTOYAGE_TEST"]
        assert "COMMIT;" in scripts["NETTOYAGE_TEST"]
        assert "RAISE EXCEPTION" in scripts["NETTOYAGE_TEST"]
        assert not re.search(r"(?im)^\s*(DROP|TRUNCATE|ALTER)\s+",
                             scripts["NETTOYAGE_TEST"])
        assert "SELECT" in scripts["AUDIT"]
        assert not re.search(r"(?im)^\s*(DELETE|UPDATE|INSERT|DROP|TRUNCATE)\s+",
                             scripts["AUDIT"])
        for phase in ("SESSION_A", "SESSION_B"):
            source = scripts[phase]
            assert "BEGIN;" in source
            assert "SET LOCAL ROLE service_role;" in source
            assert "COMMIT;" in source
            assert "statement_timeout" in source


def test_parallel_order_reuses_same_key_and_payload():
    a = (ROOT / "20261105_concurrence_commande_SESSION_A.sql").read_text(encoding="utf-8")
    b = (ROOT / "20261105_concurrence_commande_SESSION_B.sql").read_text(encoding="utf-8")
    for sql in (a, b):
        assert "erp_create_sales_order" in sql
        assert "'IT26_PAR_ORDER'" in sql
        assert "'IT26_PAR_CLIENT'" in sql
        assert "'IT26_PAR_SKU'" in sql
    assert "pg_sleep(5)" in a


def test_parallel_payment_uses_different_operation_keys_same_bank_reference():
    a = (ROOT / "20261105_concurrence_finance_SESSION_A.sql").read_text(encoding="utf-8")
    b = (ROOT / "20261105_concurrence_finance_SESSION_B.sql").read_text(encoding="utf-8")
    assert "'IT26_PAR_PAY_A'" in a
    assert "'IT26_PAR_PAY_B'" in b
    for sql in (a, b):
        assert "erp_finance_transaction" in sql
        assert "'IT26_PAR_FINREF'" in sql
        assert "'IT26_PAR_BANK'" in sql
    assert "pg_sleep(5)" in a
