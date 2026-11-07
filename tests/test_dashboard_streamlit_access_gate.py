"""Vérifie le véritable point d'entrée Streamlit des dashboards sans session réelle.

Les interactions de rendu sont substituées ; aucune donnée n'est lue en production.
"""
from contextlib import contextmanager
import pytest
from modules.dashboards import views, service


@pytest.mark.parametrize("role", ["", "COMMERCIAL", "INCONNU"])
def test_dashboards_deny_before_tabs(monkeypatch, role):
    messages = []
    monkeypatch.setattr(views.st, "session_state", {"user": {"role": role}})
    monkeypatch.setattr(views.st, "title", lambda *args, **kwargs: None)
    monkeypatch.setattr(views.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(views.st, "error", lambda msg: messages.append(msg))
    monkeypatch.setattr(views, "has_permission",
                        lambda r, m, p: False if (m, p) == ("Dashboards", "lecture") else pytest.fail("RBAC incorrect"))
    monkeypatch.setattr(views.st, "tabs", lambda *a, **kw: pytest.fail("Onglets ouverts malgré refus"))
    assert views._show_dashboards_page_impl() is None
    assert len(messages) == 1
    assert "accès" in messages[0].lower()


def test_authorized_role_reaches_tab_creation(monkeypatch):
    class TabsReached(Exception):
        pass

    checks = []
    monkeypatch.setattr(views.st, "session_state", {"user": {"role": "ADMIN"}})
    monkeypatch.setattr(views.st, "title", lambda *args, **kwargs: None)
    monkeypatch.setattr(views.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(views, "has_permission",
                        lambda role, module, perm: checks.append((role, module, perm)) or True)

    def at_tabs(labels):
        assert len(labels) == 9
        raise TabsReached()

    monkeypatch.setattr(views.st, "tabs", at_tabs)
    with pytest.raises(TabsReached):
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
