"""Incident 2026-11-08 : un TypeError du diagnostic n'arrête pas le Dashboard.

Tests hors réseau et sans identité réelle. Les gardes strictes restent obligatoires.
"""
from __future__ import annotations

import pytest

from core.strict_reads import DataReadError
from modules.dashboards import service, views


def test_incompatible_projection_uses_strict_full_read(monkeypatch):
    calls = []

    def incompatible(table):
        calls.append(("projection", table))
        return []

    def strict_full(table):
        calls.append(("strict", table))
        if table == "factures":
            return [{"facture_id": "DEMO-TEST-1", "statut": "VALIDE"}]
        return []

    monkeypatch.setattr(service, "fetch_provenance_identifiers", incompatible)
    monkeypatch.setattr(service, "fetch_data", strict_full)
    with service.dashboard_read_scope():
        result = service.get_dashboard_data_provenance()
        second = service.get_dashboard_data_provenance()
    assert result == second
    assert result["marked"] == 1
    assert len(result["sources"]) == 6
    expected = [table for table, _, _ in service._PROVENANCE_SOURCES]
    # Une signature obsolète rejette le mot clé avant d'entrer dans la fonction.
    assert calls == [("strict", table) for table in expected]


def test_fallback_permission_denial_does_not_report_zero(monkeypatch):
    def incompatible(_table):
        raise TypeError("old-signature")  # Ne jamais diffuser ce message.

    monkeypatch.setattr(service, "fetch_provenance_identifiers", incompatible)

    def denied(_table):
        raise PermissionError("Accès refusé")

    monkeypatch.setattr(service, "fetch_data", denied)
    with service.dashboard_read_scope():
        for _ in range(2):
            with pytest.raises(PermissionError):
                service.get_dashboard_data_provenance()


def test_fallback_incomplete_read_does_not_cache(monkeypatch):
    attempts = []

    def incompatible(_table):
        raise TypeError("old-signature")

    def incomplete(table):
        attempts.append(table)
        raise DataReadError("Page incomplète")

    monkeypatch.setattr(service, "fetch_provenance_identifiers", incompatible)
    monkeypatch.setattr(service, "fetch_data", incomplete)
    with service.dashboard_read_scope():
        for _ in range(2):
            with pytest.raises(DataReadError):
                service.get_dashboard_data_provenance()
    assert attempts == ["factures", "factures"]


def test_type_error_diagnostic_shows_not_verified_but_allows_navigation(monkeypatch):
    class PanelReached(Exception):
        pass

    visible_warnings = []
    monkeypatch.setattr(views.st, "session_state", {"user": {"role": "ADMIN"}})
    monkeypatch.setattr(views.st, "title", lambda *a, **kw: None)
    monkeypatch.setattr(views.st, "caption", lambda *a, **kw: None)
    monkeypatch.setattr(views.st, "toggle", lambda *a, **kw: False)
    monkeypatch.setattr(views.st, "warning",
                        lambda value, **_kw: visible_warnings.append(str(value)))
    monkeypatch.setattr(views, "has_permission", lambda *_args: True)

    def broken_diagnostic():
        raise TypeError("internal-private-value")

    monkeypatch.setattr(views, "get_dashboard_data_provenance", broken_diagnostic)

    def navigate(*args, **kwargs):
        assert args[0] == "Vue du tableau de bord"
        raise PanelReached()

    monkeypatch.setattr(views.st, "selectbox", navigate)
    with pytest.raises(PanelReached):
        views._show_dashboards_page_impl()
    assert len(visible_warnings) == 1
    assert "non vérifiable" in visible_warnings[0]
    assert "ne sont pas certifiés" in visible_warnings[0]
    assert "internal-private-value" not in visible_warnings[0]


def test_denied_role_still_blocks_before_diagnostic(monkeypatch):
    monkeypatch.setattr(views.st, "session_state", {"user": {"role": "INCONNU"}})
    monkeypatch.setattr(views.st, "title", lambda *a, **kw: None)
    monkeypatch.setattr(views.st, "caption", lambda *a, **kw: None)
    monkeypatch.setattr(views.st, "error", lambda *a, **kw: None)
    monkeypatch.setattr(views, "has_permission", lambda *_args: False)
    monkeypatch.setattr(views, "get_dashboard_data_provenance",
                        lambda: pytest.fail("Diagnostic interdit sans accès"))
    monkeypatch.setattr(views.st, "selectbox",
                        lambda *a, **kw: pytest.fail("Sélecteur interdit sans accès"))
    assert views._show_dashboards_page_impl() is None
