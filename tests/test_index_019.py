"""Contrats statiques sur les index additifs SCF et paie."""
from pathlib import Path

SQL=(Path(__file__).resolve().parents[1]/"sql"/"019_indexes_scf_paie.sql").read_text(encoding="utf-8")


def test_index_019_additif():
    for name in ("scf_pieces_code_journal_idx", "scf_lignes_compte_idx",
                 "paie_bulletins_v2_periode_id_idx", "scf_pieces_validees_date_idx"):
        assert f"CREATE INDEX IF NOT EXISTS {name}" in SQL
    for unsafe in ("DROP TABLE", "TRUNCATE", "UPDATE public.", "DELETE FROM public."):
        assert unsafe not in SQL


def test_indexes_sur_nouvelles_tables_seulement():
    assert "ON public.scf_pieces" in SQL
    assert "ON public.scf_lignes" in SQL
    assert "ON public.paie_bulletins_v2" in SQL
    assert SQL.strip().endswith("COMMIT;")
