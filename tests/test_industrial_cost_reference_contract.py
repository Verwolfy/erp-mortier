"""Tests statiques du referentiel de couts industriels."""
from decimal import Decimal
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_schema_contract():
    sql = (ROOT / "sql" / "034_referentiel_couts_industriels_analytiques.sql").read_text(encoding="utf-8")
    sql2 = (ROOT / "sql" / "035_cout_industriel_synthese_validation.sql").read_text(encoding="utf-8")
    for name in ("erp_cost_periods", "erp_cost_natures", "erp_cost_pools", "erp_cost_drivers"):
        assert name in sql
    for key in ("UNITS", "KG", "HOURS_LABOR", "HOURS_MACHINE", "KWH", "DIRECT_COST"):
        assert key in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "security_invoker = true" in sql
    assert "erp_cost_of_summary" in sql2
    assert "DOCUMENTE" in sql2
    assert "NULLIF(o.quantite_produite,0)" in sql2

def test_allocation_math():
    a = Decimal(120)*2/6 + Decimal(90)*1/3
    b = Decimal(120)*4/6 + Decimal(90)*2/3
    assert (a,b,a+b) == (70,140,210)
    assert (Decimal(300)+a)/10 == 37
    assert (Decimal(200)+b)/5 == 68

def test_production_tab_and_auth():
    page = (ROOT / "modules" / "production" / "views.py").read_text(encoding="utf-8")
    ui = (ROOT / "modules" / "production" / "cost_views.py").read_text(encoding="utf-8")
    srv = (ROOT / "modules" / "production" / "cost_service.py").read_text(encoding="utf-8")
    assert "show_cost_reference(can_write)" in page
    assert 'check_server_permission("comptes")' in srv
    assert 'check_server_read_permission("comptes")' in srv
    assert "document_pool" in ui and "validate_period" in ui
