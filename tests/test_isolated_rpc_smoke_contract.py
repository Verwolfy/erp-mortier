"""Contrats de sécurité pour les vrais scénarios RPC sur erp-mortier-test.

Ces tests ne déclenchent aucun accès réseau ni opération sur Supabase.
L'exécution SQL réelle se fait séparément sur le projet isolé.
"""
from pathlib import Path
import re

SCRIPTS = Path(__file__).resolve().parents[1] / "sql" / "test_isole"
NAMES = (
    "20261105_test_achat_reception_RB.sql",
    "20261105_test_production_qualite_RB.sql",
    "20261105_test_vente_finance_RB.sql",
)


def test_all_transaction_tests_must_rollback_and_name_only_test_project():
    for name in NAMES:
        text = (SCRIPTS / name).read_text(encoding="utf-8")
        noncomment = "\n".join(
            line for line in text.splitlines()
            if not line.lstrip().startswith("--")
        ).strip()
        assert "ffuhbmcfyexsbjwhryvj" in text
        assert re.search(r"(?m)^BEGIN;\s*$", noncomment)
        assert re.search(r"(?m)^ROLLBACK;\s*$", noncomment)
        assert not re.search(r"(?im)^\s*COMMIT\s*;", noncomment)
        assert noncomment.endswith("ROLLBACK;")
        assert "SET LOCAL ROLE service_role;" in noncomment
        assert "RESET ROLE;" in noncomment
        assert "statement_timeout" in noncomment
        assert "IT26_" in noncomment


def test_each_business_process_exercises_live_replay_and_invariants():
    purchase = (SCRIPTS / NAMES[0]).read_text(encoding="utf-8")
    production = (SCRIPTS / NAMES[1]).read_text(encoding="utf-8")
    sales = (SCRIPTS / NAMES[2]).read_text(encoding="utf-8")
    for rpc in ("erp_create_purchase_order", "erp_receive_purchase_order"):
        assert purchase.count(rpc + "(") >= 3
    assert "PARTIELLEMENT_RECEPTIONNE" in purchase
    assert "RECEPTIONNE" in purchase
    assert "unique_violation" in purchase
    for rpc in ("erp_create_recipe", "erp_create_manufacturing_order",
                "erp_start_manufacturing_order", "erp_close_manufacturing_order"):
        assert production.count(rpc + "(") >= 2
    assert "TERMINE" in production
    assert "unique_violation" in production
    assert "check_violation" in production
    for rpc in ("erp_create_sales_order", "erp_sale_transaction",
                "erp_finance_transaction"):
        assert sales.count(rpc + "(") >= 3
    assert "'SHIP'" in sales and "'DRAFT'" in sales
    assert "'VALIDATE'" in sales and "'PAYMENT'" in sales
    assert "'ALLOCATE'" in sales
    assert "unique_violation" in sales and "check_violation" in sales


def test_transient_permissions_are_transaction_bounded():
    production = (SCRIPTS / NAMES[1]).read_text(encoding="utf-8")
    sales = (SCRIPTS / NAMES[2]).read_text(encoding="utf-8")
    for sql in (production, sales):
        assert sql.index("BEGIN;") < sql.index("GRANT UPDATE")
        assert sql.index("GRANT UPDATE") < sql.index("SET LOCAL ROLE service_role;")
        assert sql.rfind("ROLLBACK;") > sql.rfind("RESET ROLE;")
