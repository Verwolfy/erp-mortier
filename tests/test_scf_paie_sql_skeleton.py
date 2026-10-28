"""Vérifications de conception SQL hors connexion. Elles ne valident PAS la migration en base."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCF=(ROOT/"sql"/"014_scf_journal.sql").read_text(encoding="utf-8")
PAIE=(ROOT/"sql"/"015_paie_privee.sql").read_text(encoding="utf-8")


def test_scf_tables_nouvelles():
    for name in ("scf_exercices","scf_plan_comptes","scf_journaux","scf_pieces","scf_lignes"):
        assert f"CREATE TABLE IF NOT EXISTS public.{name}" in SCF
        assert f"ALTER TABLE public.{name} ENABLE ROW LEVEL SECURITY" in SCF


def test_scf_triggers_verrou_validation():
    assert "OLD.statut='VALIDEE'" in SCF
    assert "v_debit<>v_credit" in SCF
    assert "NEW.statut <> 'BROUILLON'" in SCF
    assert "CREATE TRIGGER scf_lignes_immutabilite" in SCF
    assert "CREATE TRIGGER scf_pieces_immutabilite" in SCF
    assert "BEFORE INSERT OR UPDATE OR DELETE ON public.scf_pieces" in SCF


def test_paie_tables_privees():
    for name in ("paie_periodes_v2","paie_bulletins_v2","paie_lignes_v2"):
        assert f"CREATE TABLE IF NOT EXISTS public.{name}" in PAIE
        assert f"ALTER TABLE public.{name} ENABLE ROW LEVEL SECURITY" in PAIE
    assert "REVOKE ALL ON public.paie_periodes_v2" in PAIE
    assert "FROM PUBLIC, anon, authenticated" in PAIE


def test_paie_immutabilite_et_preuves():
    for phrase in ("NEW.statut <> 'PREPARE'", "OLD.statut='VALIDE'",
                   "preuve_calcul->>'statut_irg'", "source_cnas",
                   "CREATE TRIGGER paie_v2_immutabilite_lignes"):
        assert phrase in PAIE


def test_aucune_table_existante_modifiee():
    for sql in (SCF,PAIE):
        for forbidden in ("DROP TABLE", "TRUNCATE", "DELETE FROM public.",
                          "ALTER TABLE public.factures", "UPDATE public.factures",
                          "ALTER TABLE public.fiches_de_paie"):
            assert forbidden not in sql

def test_clotures_non_reouvrables():
    assert "Exercice cloture immuable" in SCF
    assert "Periode de paie cloturee immuable" in PAIE
    assert "scf_exercices_cloture" in SCF
    assert "paie_v2_cloture_periodes" in PAIE


def test_validation_ne_permet_pas_de_falsifier_les_montants():
    for field in ("piece_id", "exercice_id", "date_ecriture", "reference", "document_source"):
        assert f"NEW.{field} IS DISTINCT FROM OLD.{field}" in SCF
    for field in ("salaire_brut", "assiette_irg", "irg", "net_a_payer", "preuve_calcul"):
        assert f"NEW.{field} IS DISTINCT FROM OLD.{field}" in PAIE
    assert "Validation SCF : modification simultanee interdite" in SCF
    assert "Validation paie : modification simultanee interdite" in PAIE


def test_preflight_registres_ne_modifie_rien():
    query = (ROOT/"sql"/"016_preflight_registres_readonly.sql").read_text(encoding="utf-8")
    code = "\n".join(
        line for line in query.splitlines() if not line.lstrip().startswith("--")
    ).upper()
    assert "WITH ATTENDUES" in code
    assert "FROM ATTENDUES" in code
    for mot in ("CREATE ", "ALTER ", "INSERT ", "UPDATE ", "DELETE ",
                "DROP ", "TRUNCATE ", "GRANT ", "REVOKE ", "DO $$"):
        assert mot not in code
