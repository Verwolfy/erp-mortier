"""Garanties statiques du retour arrière du jeu DEMO26.

N'exécute aucun SQL : les opérations réelles de suppression exigent un acte séparé.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1] / "sql" / "demo"
SEED = ROOT / "20261105_seed_erp_kpi_FICTIF.sql"
UNDO = ROOT / "20261105_rollback_erp_kpi_FICTIF.sql"
INSERT = re.compile(r"^INSERT INTO public\.([a-z_][a-z_0-9]*)\s*\(", re.M)
DELETE = re.compile(r"^DELETE FROM public\.([a-z_][a-z_0-9]*)\s+WHERE\s+([^;]+);", re.M)


def test_rollback_covers_every_demo_table_in_reverse_dependency_order():
    seed, undo = SEED.read_text(encoding="utf-8"), UNDO.read_text(encoding="utf-8")
    insert_tables = INSERT.findall(seed)
    delete_tables = [name for name, _ in DELETE.findall(undo)]
    assert len(insert_tables) == len(delete_tables) == 53
    assert len(insert_tables) == len(set(insert_tables))
    assert delete_tables == list(reversed(insert_tables))


def test_rollback_is_id_bounded_and_never_cascades_or_alters_schema():
    undo = UNDO.read_text(encoding="utf-8")
    statements = DELETE.findall(undo)
    assert undo.count("DELETE FROM public.") == 53
    for table, condition in statements:
        assert re.fullmatch(r"[a-z_][a-z_0-9]*\s+IN\s*\(.+\)(?:\s+AND\s+date_effet='2026-11-01')?", condition, re.S)
        assert ("DEMO26_" in condition or "90000000-0026-" in condition
                or "41199926" in condition or "70199926" in condition
                or "-26000" in condition)
    cleaned = re.sub(r"(?m)^--[^\n]*$", "", undo).strip()
    cleaned = DELETE.sub("", cleaned).replace("BEGIN;", "").replace("COMMIT;", "").strip()
    assert not cleaned
    assert "CASCADE" not in re.sub(r"(?m)^--[^\n]*$", "", undo).upper()


def test_seed_never_updates_or_deletes_existing_records():
    seed = SEED.read_text(encoding="utf-8")
    assert seed.count("INSERT INTO public.") == 53
    assert "DO $guard$" in seed
    assert "OVERRIDING SYSTEM VALUE" in seed
    assert not re.search(r"(?im)^\s*(UPDATE|DELETE|TRUNCATE|DROP|ALTER)\s+", seed)
    assert seed.strip().endswith("COMMIT;")


def test_complete_80_row_rollback_is_exactly_two_lots():
    """Le rollback tout-en-un conserve l'ordre et les prédicats des deux lots."""
    lot2 = (ROOT / "20261105_rollback_stock_opening_lot2_FICTIF.sql").read_text(encoding="utf-8")
    lot1 = UNDO.read_text(encoding="utf-8")
    combined = (ROOT / "20261105_rollback_COMPLET_80_lignes_FICTIF.sql").read_text(encoding="utf-8")
    expected = DELETE.findall(lot2) + DELETE.findall(lot1)
    actual = DELETE.findall(combined)
    assert len(expected) == len(actual) == 55
    assert actual == expected
    assert combined.count("BEGIN;") == combined.count("COMMIT;") == 1
    assert "CASCADE" not in re.sub(r"(?m)^--[^\n]*$", "", combined).upper()


def test_second_lot_only_adds_two_traced_stock_movements():
    lot2 = (ROOT / "20261105_stock_opening_lot2_FICTIF.sql").read_text(encoding="utf-8")
    assert INSERT.findall(lot2) == ["mouvements", "mouvements_pf"]
    assert "DEMO26_MV2" in lot2 and "DEMO26_MVP2" in lot2
    assert "DEMO26_STOCK_INITIAL" in lot2
    assert not re.search(r"(?im)^\s*(UPDATE|DELETE|TRUNCATE|DROP|ALTER)\s+", lot2)
    assert lot2.strip().endswith("COMMIT;")


def test_exact_80_line_verification_matches_every_rollback_predicate():
    """Le contrôle SQL doit couvrir chaque prédicat de suppression, sans omission."""
    source = (ROOT / "20261105_verification_EXACTE_80_lignes_FICTIF.sql").read_text(encoding="utf-8")
    rollback = (ROOT / "20261105_rollback_COMPLET_80_lignes_FICTIF.sql").read_text(encoding="utf-8")
    predicates = DELETE.findall(rollback)
    assert len(predicates) == 55
    for table, condition in predicates:
        assert f"FROM public.{table} WHERE {condition}) AS observe" in source
    assert source.count(" AS observe") == 55
    assert "nombre_tables = 53" in source
    assert "total_attendu = 80" in source
    assert "total_present = 80" in source
    assert "anomalies = 0" in source
    assert not re.search(r"(?im)^\s*(DELETE|UPDATE|INSERT|TRUNCATE|ALTER|DROP)\s+", source)


def test_new_integrated_cycle_has_exact_40_reversible_rows():
    seed = (ROOT / "20261105_seed_cycle_complet_SIM26_FICTIF.sql").read_text(encoding="utf-8")
    undo = (ROOT / "20261105_rollback_cycle_complet_SIM26_FICTIF.sql").read_text(encoding="utf-8")
    insertions = INSERT.findall(seed)
    removals = DELETE.findall(undo)
    assert len(insertions) == len(removals) == 40
    assert len(set(insertions)) == 37
    assert [table for table, _ in removals] == list(reversed(insertions))
    assert seed.count("BEGIN;") == seed.count("COMMIT;") == 1
    assert undo.count("BEGIN;") == undo.count("COMMIT;") == 1
    assert all("SIM26_" in condition for _, condition in removals)


def test_full_120_rollback_concatenates_both_in_dependency_order():
    undo40 = (ROOT / "20261105_rollback_cycle_complet_SIM26_FICTIF.sql").read_text(encoding="utf-8")
    undo80 = (ROOT / "20261105_rollback_COMPLET_80_lignes_FICTIF.sql").read_text(encoding="utf-8")
    undo120 = (ROOT / "20261105_rollback_TOTAL_120_lignes_FICTIVES.sql").read_text(encoding="utf-8")
    assert len(DELETE.findall(undo120)) == 95
    assert DELETE.findall(undo120) == DELETE.findall(undo40) + DELETE.findall(undo80)
    assert undo120.count("BEGIN;") == undo120.count("COMMIT;") == 1
    assert not any(line.strip().startswith(("ALTER", "TRUNCATE", "DROP"))
                   for line in undo120.splitlines())


def test_sim26_verification_is_read_only_and_has_full_identity_coverage():
    sql = (ROOT / "20261105_verification_cycle_complet_SIM26_FICTIF.sql").read_text(encoding="utf-8")
    undo = (ROOT / "20261105_rollback_cycle_complet_SIM26_FICTIF.sql").read_text(encoding="utf-8")
    for table, condition in DELETE.findall(undo):
        assert f"FROM public.{table} WHERE {condition}" in sql
    assert sql.count(" AS n") == 40
    assert "received_mp" in sql and "delivered_pf" in sql
    assert "allocated" in sql and "settlement_total" in sql
    assert not re.search(r"(?im)^\s*(DELETE|UPDATE|INSERT|TRUNCATE|ALTER|DROP)\s+", sql)
