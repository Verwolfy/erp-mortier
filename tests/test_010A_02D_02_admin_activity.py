"""Tests des callbacks Administration."""
import ast
from collections import Counter
from pathlib import Path


def _tree():
    root = Path(__file__).resolve().parents[1]
    return ast.parse(
        (root / "modules/admin/views.py").read_text(
            encoding="utf-8-sig"
        )
    )


def test_admin_eight_callbacks():
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
                kw.arg == "on_click"
                and isinstance(kw.value, ast.Name)
                and kw.value.id == "_mark_admin_activity"
            ):
                counts[node.func.attr] += 1

    assert counts == Counter({
        "button": 4,
        "form_submit_button": 4,
    })


def test_sensitive_forms_without_callbacks():
    expected = {"form_add_user", "form_add_perm"}
    found = set()

    for node in ast.walk(_tree()):
        if not isinstance(node, ast.With):
            continue

        for item in node.items:
            call = item.context_expr
            if not isinstance(call, ast.Call):
                continue
            if not isinstance(call.func, ast.Attribute):
                continue
            if call.func.attr != "form":
                continue
            if not call.args or not isinstance(call.args[0], ast.Constant):
                continue

            name = call.args[0].value
            if name not in expected:
                continue

            found.add(name)

            submits = [
                child for child in ast.walk(node)
                if (
                    isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Attribute)
                    and child.func.attr == "form_submit_button"
                )
            ]

            assert len(submits) == 1
            assert not any(
                kw.arg == "on_click"
                for kw in submits[0].keywords
            )

    assert found == expected


def test_admin_callback_no_direct_refresh():
    functions = [
        node for node in _tree().body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_mark_admin_activity"
    ]

    assert len(functions) == 1
    code = ast.unparse(functions[0])

    assert "last_activity" not in code
    assert "_erp_admin_interacted" in code
