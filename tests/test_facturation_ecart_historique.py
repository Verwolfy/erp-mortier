"""Inventaire explicite des conventions fiscales historiques, sans les approuver.

Ce test échoue si un taux historique est modifié silencieusement. Il ne valide
pas la légalité du calcul : le remplacement requiert une migration coordonnée.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_conventions_historiques_python_documentees():
    source = (ROOT / "modules/ventes/service.py").read_text(encoding="utf-8")
    assert 'TAUX_TVA = Decimal("0.19")' in source
    assert 'TAUX_TIMBRE = Decimal("0.01")' in source
    assert 'MAX_TIMBRE = Decimal("2500.00")' in source
    assert "tva = _money(ht * TAUX_TVA)" in source
    assert "stamp = min(_money(ttc_before_stamp * TAUX_TIMBRE), MAX_TIMBRE)" in source


def test_migration_sql_parametree_rejette_conventions_historiques():
    proposal = (ROOT / "sql/013_facturation_parametree.sql").read_text(encoding="utf-8")
    assert "v_tax := round(v_net_ht * 0.19,2)" not in proposal
    assert "v_net_ht,0.19" not in proposal
    assert "public.erp_facture_parametre(" in proposal
    assert "niveau_confiance = 'CONFIRMEE'" in proposal
