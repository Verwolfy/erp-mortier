"""Tests du suivi d'activite Production."""
import ast
from collections import Counter
from pathlib import Path


def _tree():
    root = Path(__file__).resolve().parents[1]
    path = root / "modules" / "production" / "views.py"
    return ast.parse(path.read_text(encoding="utf-8-sig"))


def test_production_fourteen_callbacks():
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

        for keyword in node.keywords:
            if keyword.arg not in ("on_click", "on_change"):
                continue
            if (
                isinstance(keyword.value, ast.Name)
                and keyword.value.id == "_mark_production_activity"
            ):
                counts[node.func.attr] += 1

    assert dict(counts) == {
        "button": 8,
        "selectbox": 4,
        "form_submit_button": 2,
    }


def test_production_callback_does_not_extend_session():
    functions = [
        node for node in _tree().body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_mark_production_activity"
    ]

    assert len(functions) == 1
    code = ast.unparse(functions[0])

    assert "last_activity" not in code
    assert "_erp_production_interacted" in code
