"""Contrats du référentiel juridique sourcé de 2026, sans données fictives.

Les tests de syntaxe ne valident pas une classification TVA des produits.
"""
from pathlib import Path
import re
import pytest

SQL = (Path(__file__).resolve().parents[1] / "sql" /
       "021_referentiels_2026_officiels.sql").read_text(encoding="utf-8")


def test_sql_021_parsable():
    pglast = pytest.importorskip("pglast")
    assert len(pglast.parse_sql(SQL)) >= 5


def test_taux_2026_officiels_explicites():
    assert "('TVA_TAUX_NORMAL', 'TVA', 0.19" in SQL
    assert "('TVA_TAUX_REDUIT', 'TVA', 0.09" in SQL
    assert SQL.count("https://www.mfdgi.gov.dz/fr/professionnels/services-pro/regime-reel/la-taxe-sur-la-valeur-ajoutee") >= 2
    assert "'2026-10-29'::date" in SQL
    assert "statut_juridique" in SQL
    assert "'CONFIRMEE'" in SQL


def test_ancienne_formule_ne_peut_pas_etre_activee():
    # Les deux taux sont des références : aucune classification 'TVA_VENTE_TAUX'
    # applicable automatiquement à toute facture.
    assert "TVA_VENTE_TAUX" not in SQL
    assert "TIMBRE_ESPECES_PLAFOND" not in SQL
    assert "TIMBRE_ESPECES_TAUX" not in SQL
    assert "erp_sale_transaction" not in SQL


def test_comptes_officiels_inactifs_par_defaut():
    assert "INSERT INTO public.scf_plan_comptes" in SQL
    for account in ("401", "411", "421", "431", "445", "512",
                    "53", "601", "631", "635", "701", "355", "381"):
        assert re.search(r"\('" + account + r"', '.+?', false, false\)", SQL)
    assert SQL.count("false, false)") >= 25
    assert "UPDATE public.scf_plan_comptes" not in SQL
    assert "DELETE FROM public.scf_plan_comptes" not in SQL


def test_pas_de_donnees_fiscales_entreprise_fictives():
    for word in ("INSERT INTO public.factures", "INSERT INTO public.employes",
                 "INSERT INTO public.scf_exercices",
                 "INSERT INTO public.scf_journaux",
                 "INSERT INTO public.scf_pieces",
                 "INSERT INTO public.scf_lignes",
                 "DROP TABLE", "TRUNCATE", "GRANT ALL", "DISABLE ROW LEVEL SECURITY"):
        assert word not in SQL


def test_anti_ecrasement_et_atomicite():
    assert "BEGIN;" in SQL
    assert SQL.rstrip().endswith("COMMIT;")
    assert SQL.count("ON CONFLICT") == 3
    assert "DO UPDATE" not in SQL
    assert "DO $verification$" in SQL
    assert "Collision" in SQL
    assert "NON_CLASSEE" in SQL
