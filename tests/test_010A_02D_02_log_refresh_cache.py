"""Regression du bouton de rafraichissement des logs."""
import ast
from pathlib import Path


def test_log_refresh_without_global_cache_purge():
    path = (
        Path(__file__).resolve().parents[1]
        / "modules/admin/views.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))

    found = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        if not isinstance(node.test, ast.Call):
            continue
        if ast.unparse(node.test.func) != "st.button":
            continue

        callback = any(
            kw.arg == "on_click"
            and isinstance(kw.value, ast.Name)
            and kw.value.id == "_mark_admin_activity"
            for kw in node.test.keywords
        )

        if callback and len(node.body) == 1:
            if isinstance(node.body[0], ast.Pass):
                found.append(node)

    assert len(found) == 1

    reads = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and ast.unparse(n.func) == "get_audit_logs"
        and 0 < n.lineno - found[0].lineno <= 6
    ]

    assert len(reads) == 1
