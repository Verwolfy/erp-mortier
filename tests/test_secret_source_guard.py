"""P0 : le garde AST échoue sur les secrets codés en dur sans les afficher."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.audit_credentials_source import main, suspicious_assignment_lines

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("source", [
    'password = "faux-secret-de-test"',
    'mot_de_passe_clair = "valeur-factice"',
    'api_key: str = "cle-de-test"',
    "token = 123456789",
])
def test_catches_direct_sensitive_literals(source):
    assert suspicious_assignment_lines(source) == [1]


def test_accepts_masked_input():
    assert suspicious_assignment_lines(
        'from getpass import getpass\npassword = getpass("Saisie : ")'
    ) == []


def test_mdp_protected_by_ast_guard():
    source = (ROOT / "mdp.py").read_text(encoding="utf-8")
    assert suspicious_assignment_lines(source) == []


def test_cli_masks_detected_value(tmp_path, capsys):
    path = tmp_path / "fixture.py"
    path.write_text('password = "faux-secret-pour-test"\n', encoding="utf-8")
    assert main([str(path)]) == 1
    output = capsys.readouterr().out
    assert "faux-secret-pour-test" not in output
    assert "lignes 1" in output


def test_cli_accepts_safe_mdp(capsys):
    assert main([str(ROOT / "mdp.py")]) == 0
    assert "OK :" in capsys.readouterr().out
