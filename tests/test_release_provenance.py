"""Version réellement observée : tests offline, sans accès à GitHub ni Supabase."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from core import release_provenance as release

A = "a" * 40
B = "b" * 40


@pytest.mark.parametrize("invalid", [None, "", "a" * 12, "x" * 40, "a" * 41, 123, A + "\n"])
def test_invalid_sha_is_never_recognized(invalid):
    assert release._sha(invalid) is None


def test_release_version_checkout_matches_expected():
    result = release.resolve_release(environ={"ERP_RELEASE_EXPECTED_SHA": A},
                                     checkout_sha=A.upper())
    assert result.sha == A
    assert result.status == "CHECKOUT CONFORME"
    assert result.source == "checkout Git local"


def test_checkout_differs_from_release_fails_visible_status():
    result = release.resolve_release(environ={"ERP_RELEASE_EXPECTED_SHA": B},
                                     checkout_sha=A)
    assert result.sha == A
    assert result.status == "ÉCART DE VERSION"


def test_git_observation_overrides_potentially_inaccurate_declaration():
    result = release.resolve_release(
        environ={"ERP_DEPLOY_SHA": B, "ERP_RELEASE_EXPECTED_SHA": A},
        checkout_sha=A,
    )
    assert result.sha == A
    assert result.status == "CHECKOUT CONFORME"


def test_env_only_declaration_never_counts_as_verified():
    result = release.resolve_release(
        environ={"ERP_DEPLOY_SHA": A, "ERP_RELEASE_EXPECTED_SHA": A},
    )
    assert result.sha == A
    assert result.source == "déclaration non prouvée"
    assert result.status == "NON VÉRIFIÉ"


def test_env_only_divergence_is_distinguished_from_local_checkout():
    result = release.resolve_release(
        environ={"ERP_DEPLOY_SHA": A, "ERP_RELEASE_EXPECTED_SHA": B},
    )
    assert result.status == "ÉCART DÉCLARÉ"


def test_unknown_version_cannot_look_verified():
    result = release.resolve_release(environ={}, checkout_sha=None)
    assert result.sha is None
    assert result.status == "NON VÉRIFIABLE"
    caption = release.release_caption(environ={}, checkout_sha="")
    assert "inconnue" in caption
    assert "NON VÉRIFIABLE" in caption


def test_invalid_expected_sha_is_rejected_even_with_git():
    result = release.resolve_release(
        environ={"ERP_RELEASE_EXPECTED_SHA": "invalid", "ERP_DEPLOY_SHA": B},
        checkout_sha=A,
    )
    assert result.status == "SHA attendu invalide"
    assert result.sha == A


def test_release_caption_contains_full_checkout_hash_not_secret():
    caption = release.release_caption(
        environ={"ERP_RELEASE_EXPECTED_SHA": A, "PRIVATE_SECRET": "dontshow"},
        checkout_sha=A,
    )
    assert A in caption
    assert "CHECKOUT CONFORME" in caption
    assert "dontshow" not in caption


def test_local_git_lookup_is_optional_and_never_runs_without_git(monkeypatch, tmp_path):
    monkeypatch.setattr(release, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(release.subprocess, "run",
                        lambda *_args, **_kw: pytest.fail("Git shouldn't run"))
    assert release._checkout_head() is None


def test_local_git_lookup_is_bounded_and_validated(monkeypatch, tmp_path):
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(release, "_REPO_ROOT", tmp_path)
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout=A + "\n")

    monkeypatch.setattr(release.subprocess, "run", fake_run)
    assert release._checkout_head() == A
    assert calls[0][0] == ["git", "rev-parse", "HEAD"]
    assert calls[0][1]["timeout"] == 2
    assert calls[0][1]["cwd"] == tmp_path


def test_head_is_reread_after_hot_reload_without_stale_cache(monkeypatch, tmp_path):
    """Le checkout peut changer pendant que Streamlit garde le processus."""
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(release, "_REPO_ROOT", tmp_path)
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout=(A if len(calls) == 1 else B) + "\n")

    monkeypatch.setattr(release.subprocess, "run", fake_run)
    assert release._checkout_head() == A
    assert release._checkout_head() == B
    assert calls == [["git", "rev-parse", "HEAD"]] * 2


@pytest.mark.parametrize("different", [False, True])
def test_critical_disk_sources_are_compared_to_git_head(monkeypatch, tmp_path, different):
    """Comparer des objets Git, jamais une variable de déploiement déclarée."""
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(release, "_REPO_ROOT", tmp_path)
    for name in release._CRITICAL_SOURCES:
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("code de test")

    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        assert kwargs["timeout"] == 2
        assert kwargs["cwd"] == tmp_path
        if command[:2] == ["git", "rev-parse"]:
            return SimpleNamespace(returncode=0, stdout=A + "\n")
        assert command[:3] == ["git", "hash-object", "--"]
        mismatch = different and command[-1] == "modules/ventes/views.py"
        return SimpleNamespace(returncode=0, stdout=(B if mismatch else A) + "\n")

    monkeypatch.setattr(release.subprocess, "run", fake_run)
    assert release._critical_sources_match_checkout() is (not different)
    assert all(cmd[0] == "git" for cmd in commands)


def test_missing_critical_tracked_file_marks_release_inconsistent(monkeypatch, tmp_path):
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(release, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        release.subprocess, "run",
        lambda *_a, **_k: pytest.fail("Missing file must be checked before Git"),
    )
    assert release._critical_sources_match_checkout() is False


def test_source_verification_unavailable_is_not_a_success(monkeypatch, tmp_path):
    monkeypatch.setattr(release, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        release.subprocess, "run",
        lambda *_a, **_k: pytest.fail("No Git: no subprocess"),
    )
    assert release._critical_sources_match_checkout() is None


def test_mixed_sources_take_priority_even_if_expected_sha_matches():
    result = release.resolve_release(
        environ={"ERP_RELEASE_EXPECTED_SHA": A},
        checkout_sha=A,
        source_consistency=False,
    )
    assert result.status == "ÉCART SOURCES/CHECKOUT"
    assert result.sha == A


def test_live_sidebar_never_masks_source_mismatch(monkeypatch):
    monkeypatch.setattr(release, "_checkout_head", lambda: A)
    monkeypatch.setattr(release, "_critical_sources_match_checkout", lambda: False)
    caption = release.release_caption(environ={"ERP_RELEASE_EXPECTED_SHA": A})
    assert A in caption
    assert "ÉCART SOURCES/CHECKOUT" in caption
    assert "sources critiques : ÉCART AVEC GIT HEAD" in caption
    assert "CHECKOUT CONFORME" not in caption


def test_live_sidebar_reports_when_sources_match(monkeypatch):
    monkeypatch.setattr(release, "_checkout_head", lambda: A)
    monkeypatch.setattr(release, "_critical_sources_match_checkout", lambda: True)
    caption = release.release_caption(environ={"ERP_RELEASE_EXPECTED_SHA": A})
    assert "sources critiques : vérifiées sur Git HEAD" in caption
    assert "CHECKOUT CONFORME" in caption
