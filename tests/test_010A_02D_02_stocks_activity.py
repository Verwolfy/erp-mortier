"""Tests des callbacks d'activite Stocks."""
import ast
from pathlib import Path


def _stocks_tree():
    root = Path(__file__).resolve().parents[1]
    path = root / "modules" / "stocks" / "views.py"
    return ast.parse(path.read_text(encoding="utf-8-sig"))


def test_four_stocks_callbacks():
    tree = _stocks_tree()

    calls = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "st"
    ]

    callbacks = []

    for call in calls:
        for keyword in call.keywords:
            if keyword.arg in ("on_click", "on_change"):
                if isinstance(keyword.value, ast.Name):
                    if keyword.value.id == "_mark_stocks_activity":
                        callbacks.append(call.func.attr)

    assert sorted(callbacks) == sorted([
        "button", "button", "radio", "form_submit_button"
    ])


def test_stocks_callback_does_not_extend_session():
    tree = _stocks_tree()
    functions = [
        n for n in tree.body
        if isinstance(n, ast.FunctionDef)
        and n.name == "_mark_stocks_activity"
    ]

    assert len(functions) == 1
    code = ast.unparse(functions[0])
    assert "last_activity" not in code
    assert "_erp_stocks_interacted" in code
