"""Contrats statiques des neuf panneaux Streamlit : contrôle d'accès et isolation.

N'exécute ni Streamlit ni Supabase et ne remplace pas le test visuel connecté.
"""
import ast
from pathlib import Path

VIEW = Path(__file__).resolve().parents[1] / "modules" / "dashboards" / "views.py"
SECTIONS = ["Direction", "Rentabilité", "Ventes", "Achats", "Stocks",
            "Production", "CRM", "RH", "Finance"]
FUNCTIONS = ["get_kpis_direction", "get_kpis_pnl", "get_kpis_ventes",
             "get_kpis_achats", "get_kpis_stocks", "get_kpis_production",
             "get_kpis_crm", "get_kpis_rh", "get_kpis_finance"]


def test_nine_tabs_have_read_isolation_and_matching_service_calls():
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    page = next(node for node in tree.body
                if isinstance(node, ast.FunctionDef)
                and node.name == "_show_dashboards_page_impl")
    sections = []
    for node in ast.walk(page):
        if not isinstance(node, ast.With):
            continue
        contexts = [item.context_expr for item in node.items]
        if len(contexts) < 2:
            continue
        tab, read = contexts[:2]
        if (not isinstance(tab, ast.Subscript)
                or not isinstance(tab.value, ast.Name)
                or tab.value.id != "onglets"
                or not isinstance(tab.slice, ast.Constant)
                or not isinstance(tab.slice.value, int)
                or not isinstance(read, ast.Call)
                or not isinstance(read.func, ast.Name)
                or read.func.id != "read_section"):
            continue
        assert len(read.args) == 1 and isinstance(read.args[0], ast.Constant)
        calls = {call.func.id for stmt in node.body for call in ast.walk(stmt)
                 if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)}
        sections.append((tab.slice.value, read.args[0].value, calls))
    assert len(sections) == len(SECTIONS)
    assert sorted(idx for idx, _, _ in sections) == list(range(9))
    for idx, name, calls in sections:
        assert name == SECTIONS[idx]
        assert FUNCTIONS[idx] in calls


def test_page_fails_closed_before_rendering_tabs():
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    page = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                and n.name == "_show_dashboards_page_impl")
    checks = [(idx, node) for idx, node in enumerate(page.body)
              if isinstance(node, ast.If) and isinstance(node.test, ast.UnaryOp)
              and isinstance(node.test.op, ast.Not)
              and isinstance(node.test.operand, ast.Name)
              and node.test.operand.id == "can_read"]
    assert len(checks) == 1
    idx, deny = checks[0]
    assert any(isinstance(n, ast.Return) for n in deny.body)
    assert any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and n.func.id == "has_permission"
               for stmt in page.body[:idx] for n in ast.walk(stmt))
    tabs = [(i, n) for i, n in enumerate(page.body)
            if isinstance(n, ast.Assign)
            and isinstance(n.value, ast.Call)
            and isinstance(n.value.func, ast.Attribute)
            and n.value.func.attr == "tabs"]
    assert len(tabs) == 1 and idx < tabs[0][0]


def test_read_scope_wraps_complete_page():
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
              and n.name == "show_dashboards_page")
    with_nodes = [n for n in ast.walk(fn) if isinstance(n, ast.With)]
    assert len(with_nodes) == 1
    context = with_nodes[0].items[0].context_expr
    assert isinstance(context, ast.Call)
    assert isinstance(context.func, ast.Name)
    assert context.func.id == "dashboard_read_scope"
    assert any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and n.func.id == "_show_dashboards_page_impl"
               for s in with_nodes[0].body for n in ast.walk(s))


def test_categorical_dashboard_charts_keep_readable_horizontal_labels():
    """Les libellés longs ne doivent plus être compressés sous les graphiques."""
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    page = next(node for node in tree.body
                if isinstance(node, ast.FunctionDef)
                and node.name == "_show_dashboards_page_impl")
    expected = {"df_balance", "df_rep", "kpis_r", "df_pie"}
    present = set()
    for node in ast.walk(page):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "bar_chart"):
            continue
        source = ast.unparse(node.args[0]) if node.args else ""
        horizontal = any(keyword.arg == "horizontal"
                         and isinstance(keyword.value, ast.Constant)
                         and keyword.value.value is True
                         for keyword in node.keywords)
        for target in expected:
            if target in source:
                assert horizontal, f"Étiquettes verticales illisibles : {target}"
                present.add(target)
    assert present == expected
