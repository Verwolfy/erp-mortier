"""Tests du suivi d'activite Dashboard."""
import ast
from pathlib import Path


def _tree():
    root = Path(__file__).resolve().parents[1]
    return ast.parse(
        (root / "modules/dashboards/views.py").read_text(
            encoding="utf-8-sig"
        )
    )


def test_dashboard_selectbox_callback():
    widgets = [
        node for node in ast.walk(_tree())
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "st"
        and node.func.attr == "selectbox"
    ]

    assert len(widgets) == 1

    callbacks = [
        kw.value for kw in widgets[0].keywords
        if kw.arg == "on_change"
    ]

    assert len(callbacks) == 1
    assert isinstance(callbacks[0], ast.Name)
    assert callbacks[0].id == "_mark_dashboards_activity"


def test_dashboard_callback_no_direct_refresh():
    functions = [
        node for node in _tree().body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_mark_dashboards_activity"
    ]

    assert len(functions) == 1

    code = ast.unparse(functions[0])

    assert "last_activity" not in code
    assert "_erp_dashboards_interacted" in code
