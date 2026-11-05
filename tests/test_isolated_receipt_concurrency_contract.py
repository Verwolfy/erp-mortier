"""Contrat des scripts SQL de réception concurrente sur base de TEST.

Ce test pytest ne se connecte à aucune base et n'exécute aucune mutation.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1] / "sql" / "test_isole"
PREFIX = "20261105_concurrence_reception_"


def test_scripts_reception_concurrente_restent_isoles():
    phases = ("PREP", "SESSION_A", "SESSION_B", "AUDIT", "NETTOYAGE")
    scripts = {
        phase: (ROOT / (PREFIX + phase + ".sql")).read_text(encoding="utf-8")
        for phase in phases
    }
    assert all("ffuhbmcfyexsbjwhryvj" in sql for sql in scripts.values())
    for phase in ("PREP", "SESSION_A", "SESSION_B", "NETTOYAGE"):
        sql = scripts[phase]
        assert re.search(r"(?m)^BEGIN;$", sql)
        assert re.search(r"(?m)^COMMIT;$", sql)
    for phase in ("SESSION_A", "SESSION_B"):
        assert "SET LOCAL ROLE service_role;" in scripts[phase]
        assert "'IT26_RACE_PO'" in scripts[phase]
        assert "\"quantite_recue\":7" in scripts[phase]
    assert "pg_sleep(5)" in scripts["SESSION_A"]
    assert "RAISE EXCEPTION" in scripts["NETTOYAGE"]
    assert not re.search(r"(?im)^\s*(DROP|TRUNCATE|ALTER)\s+", scripts["NETTOYAGE"])
    assert not re.search(r"(?im)^\s*(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER)\s+", scripts["AUDIT"])
    assert "stock_mp" in scripts["AUDIT"]
    assert "quantite_recue" in scripts["AUDIT"]
