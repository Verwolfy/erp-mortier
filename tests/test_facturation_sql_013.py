"""Contrats statiques du correctif SQL 013, sans test DDL en base."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / "sql" / "013_facturation_parametree.sql").read_text(encoding="utf-8")


def test_remplace_la_rpc_existante_sans_ajouter_de_table():
    assert SQL.count("CREATE OR REPLACE FUNCTION public.erp_sale_transaction(") == 1
    assert "CREATE TABLE" not in SQL.upper()
    assert "DROP TABLE" not in SQL.upper()
    assert "TRUNCATE" not in SQL.upper()


def test_aucun_taux_fiscal_en_dur_dans_la_migration():
    for forbidden in ("v_net_ht * 0.19", "*0.01,2),2500", "v_net_ht,0.19"):
        assert forbidden not in SQL
    assert "v_taux_tva := public.erp_facture_parametre" in SQL
    assert "v_net_ht,v_taux_tva" in SQL


def test_date_fiscale_dans_facture_et_taux():
    assert "v_date_facture := (p_payload->>'date_facture')::date;" in SQL
    assert "p_payload->>'date_facture',v_net_ht,v_taux_tva" in SQL
    assert "v_original.taux_tva IS DISTINCT FROM v_taux_tva" in SQL


def test_parametres_non_confirmes_refuses():
    assert "statut_juridique = 'en_vigueur'" in SQL
    assert "niveau_confiance = 'CONFIRMEE'" in SQL
    assert "v_nombre <> 1 OR v_valeur IS NULL" in SQL
    assert "public.erp_facture_parametre('TIMBRE_ESPECES_PLAFOND'" in SQL


def test_rpc_service_role_seulement():
    assert "SECURITY INVOKER" in SQL
    assert "FROM PUBLIC, anon, authenticated" in SQL
    assert "TO service_role" in SQL


def test_pas_de_modification_des_montants_des_factures_anciennes():
    # Le passage de BROUILLON à VALIDE peut modifier uniquement le statut.
    # Aucune écriture en place des taux ou montants calculés n'est admise.
    compact = " ".join(SQL.split()).upper()
    for field in ("MONTANT_HT", "MONTANT_TVA", "MONTANT_TTC", "TAUX_TVA"):
        assert f"UPDATE PUBLIC.FACTURES SET {field}" not in compact
    assert "DELETE FROM public.factures" not in SQL
