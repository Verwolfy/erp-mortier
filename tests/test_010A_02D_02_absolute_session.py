"""Regression : un rerun ne doit pas prolonger la session."""
import ast
from pathlib import Path


def test_no_automatic_session_extension():
    source = Path("app.py").read_text(encoding="utf-8-sig")
    tree = ast.parse(source)

    fn = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_verified_user"
    )

    for node in ast.walk(fn):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Subscript):
                    assert ast.unparse(target) != (
                        "st.session_state['last_activity']"
                    )
