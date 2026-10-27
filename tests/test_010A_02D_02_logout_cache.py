"""Tests de non-regression de la deconnexion."""
import ast
from pathlib import Path


def _logout():
    root = Path(__file__).resolve().parents[1]
    path = root / "modules/auth/views.py"

    tree = ast.parse(
        path.read_text(encoding="utf-8-sig")
    )

    matches = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "logout"
    ]

    assert len(matches) == 1
    return matches[0]


def test_logout_has_no_global_cache_purge():
    calls = [
        ast.unparse(node.func)
        for node in ast.walk(_logout())
        if isinstance(node, ast.Call)
    ]

    assert "st.cache_data.clear" not in calls
    assert "st.cache_resource.clear" not in calls
    assert "st.rerun" in calls


def test_logout_resets_session():
    values = {}

    for node in ast.walk(_logout()):
        if not isinstance(node, ast.Assign):
            continue

        for target in node.targets:
            if not isinstance(target, ast.Subscript):
                continue

            if ast.unparse(target.value) != "st.session_state":
                continue

            key = ast.literal_eval(target.slice)
            values[key] = ast.literal_eval(node.value)

    assert values["user"] is None
    assert values["authenticated"] is False
    assert values["last_activity"] == 0
    assert values["login_attempts"] == 0
    assert values["lockout_time"] == 0
