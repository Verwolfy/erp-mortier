"""Contrat statique et valeurs de référence du test CUMP isolé.

Ne contacte ni Supabase ni un service externe.
"""
from decimal import Decimal
from pathlib import Path

SQL = (Path(__file__).resolve().parents[1] / "sql" / "test_isole" /
       "20261105_cump_approfondi_ROLLBACK.sql")


def test_cump_reference_values_and_rollback():
    s = SQL.read_text(encoding="utf-8")
    assert s.lstrip().startswith("-- Test CUMP approfondi, TEST UNIQUEMENT")
    assert "ffuhbmcfyexsbjwhryvj" in s
    assert "BEGIN;" in s
    assert s.rstrip().endswith("ROLLBACK;")
    assert "COMMIT;" not in s.upper()
    for name in ("IT26_CUMP_MP_A", "IT26_CUMP_MP_B", "IT26_CUMP_SKU"):
        assert name in s
    for term in ("CUMP_TEST_OK", "erp_apply_stock_movement",
                 "erp_stock_operations", "erp_stock_outbox",
                 "stock_actuel", "stock_actuel_pf"):
        assert term in s
    assert (Decimal(10)*100+Decimal(20)*130)/Decimal(30) == Decimal(120)
    assert (Decimal(18)*120+Decimal(6)*90)/Decimal(24) == Decimal("112.5")
    assert (Decimal("0.1")*Decimal("0.1") +
            Decimal("0.2")*Decimal("0.2")) == Decimal("0.05")
    assert (Decimal(2)*25+Decimal(3)*40)/Decimal(5) == Decimal(34)
    assert Decimal("1.5")*Decimal(34) == Decimal(51)
