"""Verification des purges de cache restantes."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MODULES = (
    "achats", "admin", "crm", "finance",
    "production", "rh", "stocks", "ventes"
)

SENSITIVE = {"form_add_user", "form_add_perm"}


def load_tree(name):
    path = ROOT / "modules" / name / "views.py"
    return ast.parse(
        path.read_text(encoding="utf-8-sig")
    )


def clear_calls(tree):
    return [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and ast.unparse(node.func) == "st.cache_data.clear"
    ]


def test_no_global_cache_purges_in_modules():
    for path in (ROOT / "modules").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        assert not clear_calls(tree), str(path)


def test_security_forms_still_submit_and_rerun():
    tree = load_tree("admin")
    found = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.With):
            continue

        for item in node.items:
            call = item.context_expr

            if not isinstance(call, ast.Call):
                continue

            if ast.unparse(call.func) != "st.form":
                continue

            if not call.args:
                continue

            if not isinstance(call.args[0], ast.Constant):
                continue

            name = call.args[0].value

            if name not in SENSITIVE:
                continue

            found.add(name)

            submits = [
                n for n in ast.walk(node)
                if isinstance(n, ast.Call)
                and ast.unparse(n.func) == "st.form_submit_button"
            ]

            assert len(submits) == 1
            assert not any(
                kw.arg == "on_click"
                for kw in submits[0].keywords
            )

            assert any(
                isinstance(n, ast.Call)
                and ast.unparse(n.func) == "st.rerun"
                for n in ast.walk(node)
            )

    assert found == SENSITIVE
