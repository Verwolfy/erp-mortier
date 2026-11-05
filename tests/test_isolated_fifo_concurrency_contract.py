"""Contrat statique des tests FIFO concurrents, sans connexion SQL."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1] / "sql" / "test_isole"
PREFIX = "20261105_concurrence_fifo_"


def test_fifo_concurrent_scripts_are_isolated_and_reversible():
    phases = ("PREP", "SESSION_A", "SESSION_B", "AUDIT", "NETTOYAGE")
    scripts = {phase: (ROOT / f"{PREFIX}{phase}.sql").read_text(encoding="utf-8") for phase in phases}
    assert all("ffuhbmcfyexsbjwhryvj" in sql or phase == "AUDIT"
               for phase, sql in scripts.items())
    for phase in ("PREP", "SESSION_A", "SESSION_B", "NETTOYAGE"):
        assert re.search(r"(?m)^BEGIN;$", scripts[phase])
        assert re.search(r"(?m)^COMMIT;$", scripts[phase])
    assert "RAISE EXCEPTION" in scripts["NETTOYAGE"]
    assert "IT26_FIFO_MP" in scripts["NETTOYAGE"]
    assert "DELETE FROM public.erp_stock_outbox" in scripts["NETTOYAGE"]
    assert "DELETE FROM public.erp_stock_operations" in scripts["NETTOYAGE"]
    assert not re.search(r"(?im)^\s*(DROP|TRUNCATE|ALTER)\s+", scripts["NETTOYAGE"])
    for phase, operation in (("SESSION_A", "IT26_FIFO_OUT_A"),
                             ("SESSION_B", "IT26_FIFO_OUT_B")):
        assert "SET LOCAL ROLE service_role;" in scripts[phase]
        assert operation in scripts[phase]
        assert "'SORTIE','IT26_FIFO_MP',6,NULL" in scripts[phase]
    assert "pg_sleep(5)" in scripts["SESSION_A"]
    assert "'2026-11-01 00:00:00'" in scripts["PREP"]
    assert "'2026-11-02 00:00:00'" in scripts["PREP"]
    assert not re.search(r"(?im)^\s*(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER)\s+", scripts["AUDIT"])
    assert "sorties_reussies=1" in scripts["AUDIT"]
    assert "stock_mp=5" in scripts["AUDIT"]
