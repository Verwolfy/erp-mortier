"""Tests des callbacks d'activite RH."""
import ast
from pathlib import Path


def _tree():
    path = (
        Path(__file__).resolve().parents[1]
        / "modules" / "rh" / "views.py"
    )
    return ast.parse(path.read_text(encoding="utf-8-sig"))


def test_rh_two_callbacks():
    callbacks = []

    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Call):
            continue

        if not isinstance(node.func, ast.Attribute):
            continue

        if node.func.attr != "form_submit_button":
            continue

        for kw in node.keywords:
            if (
                kw.arg == "on_click"
                and isinstance(kw.value, ast.Name)
                and kw.value.id == "_mark_rh_activity"
            ):
                callbacks.append(node)

    assert len(callbacks) == 2


def test_rh_callback_never_refreshes_directly():
    functions = [
        node for node in _tree().body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_mark_rh_activity"
    ]

    assert len(functions) == 1

    code = ast.unparse(functions[0])

    assert "last_activity" not in code
    assert "_erp_rh_interacted" in code
