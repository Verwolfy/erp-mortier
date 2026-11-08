"""Contrôle d'accès réel de la navigation Dashboard sans session de production."""
from contextlib import contextmanager

import pytest
from modules.dashboards import views, service


@pytest.mark.parametrize("role", ["", "COMMERCIAL", "INCONNU"])
def test_dashboards_deny_before_panel_selector(monkeypatch, role):
    messages = []
    monkeypatch.setattr(views.st, "session_state", {"user": {"role": role}})
    monkeypatch.setattr(views.st, "title", lambda *args, **kwargs: None)
    monkeypatch.setattr(views.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(views.st, "error", lambda msg: messages.append(msg))
    monkeypatch.setattr(
        views, "has_permission",
        lambda r, m, p: False if (m, p) == ("Dashboards", "lecture")
        else pytest.fail("RBAC incorrect"),
    )
    monkeypatch.setattr(
        views.st, "selectbox",
        lambda *a, **kw: pytest.fail("Navigation ouverte malgré refus"),
    )
    assert views._show_dashboards_page_impl() is None
    assert len(messages) == 1
    assert "accès" in messages[0].lower()


def test_authorized_role_reaches_lazy_panel_selector(monkeypatch):
    class PanelReached(Exception):
        pass

    checks = []
    monkeypatch.setattr(views.st, "session_state", {"user": {"role": "ADMIN"}})
    monkeypatch.setattr(views.st, "title", lambda *args, **kwargs: None)
    monkeypatch.setattr(views.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(views.st, "toggle", lambda *args, **kwargs: False)
    monkeypatch.setattr(views, "get_dashboard_data_provenance",
                        lambda: {"marked": 0})
    monkeypatch.setattr(
        views, "has_permission",
        lambda role, module, perm: checks.append((role, module, perm)) or True,
    )

    def at_panel(label, options, **kwargs):
        assert label == "Vue du tableau de bord"
        assert len(options) == 9
        assert kwargs["on_change"] is views._mark_dashboards_activity
        raise PanelReached()

    monkeypatch.setattr(views.st, "selectbox", at_panel)
    with pytest.raises(PanelReached):
        views._show_dashboards_page_impl()
    assert checks == [("ADMIN", "Dashboards", "lecture")]


def test_page_wrapper_opens_and_closes_read_scope(monkeypatch):
    events = []

    @contextmanager
    def scope(*, demo_rows=None):
        assert demo_rows is None
        events.append("enter")
        try:
            yield
        finally:
            events.append("exit")

    def render():
        events.append("render")

    monkeypatch.setattr(service, "dashboard_read_scope", scope)
    monkeypatch.setattr(views, "_show_dashboards_page_impl", render)
    views.show_dashboards_page()
    assert events == ["enter", "render", "exit"]
