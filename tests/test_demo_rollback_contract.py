"""Garanties statiques du retour arrière du jeu DEMO26.

N'exécute aucun SQL : les opérations réelles de suppression exigent un acte séparé.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1] / "sql" / "demo"
SEED = ROOT / "20261105_seed_erp_kpi_FICTIF.sql"
UNDO = ROOT / "20261105_rollback_erp_kpi_FICTIF.sql"
INSERT = re.compile(r"^INSERT INTO public\.([a-z_][a-z_0-9]*)\s+\(", re.M)
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
