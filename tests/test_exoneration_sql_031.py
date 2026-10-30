"""Contrat de sécurité du précontrôle fiscal de vente 031.

La CI couvre les invariants statiques. L'intégration PostgreSQL nécessite
l'application effective sur TEST et le smoke-test sous ROLLBACK ; une CI
verte ne prouve ni installation SQL ni conformité fiscale réelle.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / "sql" / "031_precontrole_exoneration_vente.sql").read_text("utf-8")


def test_precontrole_est_une_lecture_seule_et_ne_facture_pas():
    assert "CREATE FUNCTION public.erp_exoneration_tva_precontrole_vente" in SQL
    assert "LANGUAGE plpgsql STABLE SECURITY DEFINER" in SQL
    assert "SET search_path = pg_catalog, pg_temp" in SQL
    body = SQL.split("AS $fn$", 1)[1].split("$fn$;", 1)[0].upper()
    for verb in ("INSERT INTO", "UPDATE PUBLIC.", "DELETE FROM",
                 "TRUNCATE", "CREATE TABLE", "GRANT EXECUTE"):
        assert verb not in body
    assert "erp_sale_transaction" not in SQL
    assert "autorise_facturation',false" in SQL
    assert SQL.count("'autorise_facturation',false") >= 5


def test_exonere_jamais_un_client_ou_sku_inactif():
    assert "CLIENT_INACTIF_OU_INCONNU" in SQL
    assert "SKU_INACTIF_OU_INCONNU" in SQL
    assert "public.clients" in SQL
    assert "public.sku_conditionnement" in SQL
    assert "cardinality(p_sku_ids) NOT BETWEEN 1 AND 200" in SQL
    assert "count(DISTINCT entree.sku)" in SQL


def test_dossier_non_homologue_et_portee_partielle_refuses():
    for name in (
        "AUCUNE_PREUVE_ENREGISTREE", "ATTESTATIONS_CONCURRENTES",
        "ATTESTATION_NON_HOMOLOGUEE", "PORTEE_SKU_PARTIELLE",
        "PRECONTROLE_OK",
    ):
        assert name in SQL
    for name in ("d.date_validation>p_date_facture",
                 "d.date_verification>p_date_facture",
                 "d.valide_par=d.cree_par",
                 "d.statut<>'VALIDEE'",
                 "e.date_effet<=p_date_facture"):
        assert name in SQL
    assert "p_date_facture > CURRENT_DATE" in SQL


def test_rpc_interdite_aux_roles_navigateur():
    assert "REVOKE ALL PRIVILEGES ON FUNCTION" in SQL
    assert "FROM PUBLIC,anon,authenticated,service_role;" in SQL
    assert "TO service_role;" in SQL
    assert "has_function_privilege(" in SQL
    assert SQL.rstrip().endswith("COMMIT;")
