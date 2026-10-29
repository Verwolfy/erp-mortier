"""Tests du verrou de préactivation, sans accès à la production."""
from pathlib import Path

from scripts.preactivation_facturation import main, verifier_migration
import pytest


def test_sql_013_interdit():
    with pytest.raises(RuntimeError, match="SQL 013"):
        verifier_migration(Path("sql/013_facturation_parametree.sql"))


def test_migration_inconnue_interdite():
    with pytest.raises(RuntimeError, match="non homologuée"):
        verifier_migration(Path("sql/999_future.sql"))


@pytest.mark.parametrize("name", ["sql/013_facturation_parametree.sql", "sql/999_future.sql"])
def test_code_sortie_non_nul(name, capsys):
    assert main([name]) == 2
    assert "REFUS PRÉACTIVATION" in capsys.readouterr().err
