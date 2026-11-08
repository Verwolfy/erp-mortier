"""P0 : le générateur bcrypt ne conserve plus de mot de passe en clair."""
from __future__ import annotations

from pathlib import Path

import bcrypt
import pytest

import mdp

ROOT = Path(__file__).resolve().parents[1]


def test_password_hash_is_bcrypt_not_plaintext():
    sample = "fauxsecretPourTestUnitaire"
    hashed = mdp.hash_password(sample)
    assert hashed != sample
    assert hashed.startswith("$2")
    assert bcrypt.checkpw(sample.encode(), hashed.encode())


@pytest.mark.parametrize("invalid", ["", "x" * 73, "🚀" * 19])
def test_password_invalid_length_rejected(invalid):
    with pytest.raises(ValueError):
        mdp.hash_password(invalid)


def test_cli_output_never_contains_plaintext(monkeypatch, capsys):
    sample = "fauxsecretNePasAfficher"
    passwords = iter((sample, sample))
    monkeypatch.setattr(mdp, "getpass", lambda _prompt: next(passwords))
    monkeypatch.setattr(mdp, "hash_password", lambda _value: "hachage-factice")
    assert mdp.main() == 0
    assert sample not in capsys.readouterr().out


def test_confirmation_mismatch_never_discloses_secret(monkeypatch, capsys):
    passwords = iter(("fauxPremier", "fauxSecond"))
    monkeypatch.setattr(mdp, "getpass", lambda _prompt: next(passwords))
    assert mdp.main() == 2
    output = capsys.readouterr().out
    assert "fauxPremier" not in output and "fauxSecond" not in output


def test_mdp_does_not_embed_a_cleartext_password():
    from scripts.audit_credentials_source import suspicious_assignment_lines
    source = (ROOT / "mdp.py").read_text(encoding="utf-8")
    assert suspicious_assignment_lines(source) == []
    assert "getpass(" in source
