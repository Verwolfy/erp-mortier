"""Tests des callbacks Finance."""
import ast
from collections import Counter
from pathlib import Path


def _tree():
    root = Path(__file__).resolve().parents[1]
    path = root / "modules" / "finance" / "views.py"
    return ast.parse(path.read_text(encoding="utf-8-sig"))


def test_finance_eight_callbacks():
    counts = Counter()

    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if not isinstance(node.func.value, ast.Name):
            continue
        if node.func.value.id != "st":
            continue

        for kw in node.keywords:
            if (
                kw.arg in ("on_click", "on_change")
                and isinstance(kw.value, ast.Name)
                and kw.value.id == "_mark_finance_activity"
            ):
                counts[node.func.attr] += 1

    assert counts == Counter({
        "button": 2,
        "selectbox": 1,
        "radio": 2,
        "form_submit_button": 3,
    })


def test_finance_callback_never_refreshes_directly():
    functions = [
        n for n in _tree().body
        if isinstance(n, ast.FunctionDef)
        and n.name == "_mark_finance_activity"
    ]

    assert len(functions) == 1
    code = ast.unparse(functions[0])

    assert "last_activity" not in code
    assert "_erp_finance_interacted" in code
