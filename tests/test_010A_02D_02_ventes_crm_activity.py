"""Tests des interactions Ventes et CRM."""
import ast
from collections import Counter
from pathlib import Path
import pytest


@pytest.mark.parametrize(
    ("module", "expected"),
    [
        ("ventes", {
            "button": 9,
            "selectbox": 9,
            "form_submit_button": 2,
        }),
        ("crm", {"form_submit_button": 2}),
    ],
)
def test_010a_commercial_callback_counts(module, expected):
    path = (
        Path(__file__).resolve().parents[1]
        / "modules" / module / "views.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    callback = "_mark_" + module + "_activity"
    counts = Counter()

    for node in ast.walk(tree):
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
                and keyword.value.id == callback
            ):
                counts[node.func.attr] += 1

    assert dict(counts) == expected


@pytest.mark.parametrize("module", ["ventes", "crm"])
def test_010a_commercial_callback_no_direct_refresh(module):
    path = (
        Path(__file__).resolve().parents[1]
        / "modules" / module / "views.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    name = "_mark_" + module + "_activity"

    functions = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == name
    ]

    assert len(functions) == 1
    code = ast.unparse(functions[0])

    assert "last_activity" not in code
    assert "_erp_" + module + "_interacted" in code
