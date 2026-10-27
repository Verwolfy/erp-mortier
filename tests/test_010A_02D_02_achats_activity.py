"""Tests des callbacks d'activite Achats."""
import ast
from pathlib import Path


def _tree():
    root = Path(__file__).resolve().parents[1]
    path = root / "modules" / "achats" / "views.py"
    return ast.parse(path.read_text(encoding="utf-8-sig"))


def test_five_achats_callbacks():
    calls = [
        n for n in ast.walk(_tree())
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "st"
    ]

    callbacks = []
    for call in calls:
        for keyword in call.keywords:
            if keyword.arg not in ("on_click", "on_change"):
                continue
            if isinstance(keyword.value, ast.Name):
                if keyword.value.id == "_mark_achats_activity":
                    callbacks.append(call.func.attr)

    assert sorted(callbacks) == sorted([
        "button", "button", "button",
        "selectbox", "form_submit_button"
    ])


def test_achats_callback_does_not_extend_session():
    functions = [
        n for n in _tree().body
        if isinstance(n, ast.FunctionDef)
        and n.name == "_mark_achats_activity"
    ]

    assert len(functions) == 1
    code = ast.unparse(functions[0])
    assert "last_activity" not in code
    assert "_erp_achats_interacted" in code
