"""Tests du suivi d'activite Guide & Aide."""
import ast
from pathlib import Path


def _tree():
    root = Path(__file__).resolve().parents[1]
    return ast.parse(
        (root / "modules/help/views.py").read_text(
            encoding="utf-8-sig"
        )
    )


def test_help_document_radio_callback():
    widgets = []

    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Call):
            continue

        f = node.func
        if not isinstance(f, ast.Attribute) or f.attr != "radio":
            continue

        if not isinstance(f.value, ast.Attribute):
            continue

        if f.value.attr != "sidebar":
            continue

        if not isinstance(f.value.value, ast.Name):
            continue

        if f.value.value.id == "st":
            widgets.append(node)

    assert len(widgets) == 1

    callbacks = [
        kw.value for kw in widgets[0].keywords
        if kw.arg == "on_change"
    ]

    assert len(callbacks) == 1
    assert isinstance(callbacks[0], ast.Name)
    assert callbacks[0].id == "_mark_help_activity"


def test_help_callback_no_direct_session_refresh():
    functions = [
        node for node in _tree().body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_mark_help_activity"
    ]

    assert len(functions) == 1

    code = ast.unparse(functions[0])
    assert "last_activity" not in code
    assert "_erp_help_interacted" in code
