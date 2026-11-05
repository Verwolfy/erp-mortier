"""Campagne achat -> emballage -> recette -> OF -> cout PF.

Contrat statique sans acces a l'ERP ni a la production.
"""
from decimal import Decimal, getcontext
from pathlib import Path
import re

getcontext().prec = 35
SCRIPT = Path(__file__).resolve().parents[1] / "sql" / "test_isole" / "20261105_cout_pf_achats_emballage_recette_ROLLBACK.sql"


def test_cout_pf_purchase_recipe_campaign():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "ffuhbmcfyexsbjwhryvj" in text
    assert text.lstrip().startswith("-- TEST EXCLUSIVEMENT")
    assert re.search(r"(?m)^BEGIN;$", text)
    assert text.rstrip().endswith("ROLLBACK;")
    assert "COMMIT;" not in text.upper()
    assert "erp_create_purchase_order" in text
    assert "erp_receive_purchase_order" in text
    assert "erp_create_recipe" in text
    assert "erp_create_manufacturing_order" in text
    assert "erp_close_manufacturing_order" in text
    assert "erp_start_manufacturing_order" in text
    assert text.count("PERFORM public.erp_create_purchase_order(") == 4
    assert text.count("PERFORM public.erp_receive_purchase_order(") == 4
    assert "IT26_PFCOST_PACK" in text
    assert "IT26_PFCOST_RAW_A" in text and "IT26_PFCOST_RAW_B" in text
    first_cost = Decimal(4) * (Decimal(3)*10 + Decimal(2)*20 + 3)
    assert first_cost == Decimal(292)
    a_cmp = (Decimal(88)*10 + Decimal(100)*14)/Decimal(188)
    b_cmp = (Decimal(52)*20 + Decimal(40)*30)/Decimal(92)
    pack_cmp = (Decimal(6)*3 + Decimal(10)*5)/Decimal(16)
    second_cost = Decimal(6)*a_cmp + Decimal(4)*b_cmp + Decimal(2)*pack_cmp
    assert second_cost.quantize(Decimal("0.01")) == Decimal("178.66")
    pf_cmp = (first_cost + second_cost) / Decimal(6)
    assert abs(pf_cmp - Decimal("78.44287696577243")) < Decimal("1e-12")
    assert abs((Decimal(182)*a_cmp + Decimal(88)*b_cmp + Decimal(14)*pack_cmp + Decimal(6)*pf_cmp) - Decimal(4880)) < Decimal("1e-20")

    # Simulation analytique fictive, non imputee aux stocks.
    assert "INDIRECT_COST_OK" in text
    assert "CREATE TEMP TABLE pg_temp.it26_pf_indirect_costs" in text
    assert "ON COMMIT DROP" in text
    for nature in ("MAIN_OEUVRE", "ENERGIE", "AMORTISSEMENT",
                   "FRAIS_INDIRECTS", "FRAIS_APPROCHE"):
        assert nature in text
    assert "v_scrap_sensitivity" in text
    overhead1 = sum(map(Decimal, (40, 20, 12, 8, 16)))
    overhead2 = sum(map(Decimal, (25, 15, 10, 5, 9)))
    assert overhead1 == Decimal(96)
    assert overhead2 == Decimal(64)
    analytic_total = first_cost + second_cost + overhead1 + overhead2
    assert analytic_total.quantize(Decimal("0.01")) == Decimal("630.66")
    assert (analytic_total / 6).quantize(Decimal("0.0001")) == Decimal("105.1095")
    assert analytic_total > first_cost + second_cost
