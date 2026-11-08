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


def _panel_index(node):
    if not (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)):
        return None
    test = node.test
    if (not isinstance(test.left, ast.Name) or test.left.id != "active_panel"
            or len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq)
            or len(test.comparators) != 1):
        return None
    sub = test.comparators[0]
    if (not isinstance(sub, ast.Subscript) or not isinstance(sub.value, ast.Name)
            or sub.value.id != "_DASHBOARD_PANELS"
            or not isinstance(sub.slice, ast.Constant)
            or type(sub.slice.value) is not int):
        return None
    return sub.slice.value


def test_nine_panels_have_isolated_reads_and_matching_service_calls():
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    page = next(node for node in tree.body
                if isinstance(node, ast.FunctionDef)
                and node.name == "_show_dashboards_page_impl")
    sections = []
    for node in page.body:
        idx = _panel_index(node)
        if idx is None:
            continue
        assert len(node.body) == 1 and isinstance(node.body[0], ast.With)
        panel = node.body[0]
        assert len(panel.items) == 1
        read = panel.items[0].context_expr
        assert (isinstance(read, ast.Call)
                and isinstance(read.func, ast.Name)
                and read.func.id == "read_section")
        assert len(read.args) == 1 and isinstance(read.args[0], ast.Constant)
        calls = {call.func.id for call in ast.walk(panel)
                 if isinstance(call, ast.Call)
                 and isinstance(call.func, ast.Name)}
        sections.append((idx, read.args[0].value, calls))
    assert len(sections) == len(SECTIONS)
    assert sorted(idx for idx, _, _ in sections) == list(range(9))
    for idx, name, calls in sections:
        assert name == SECTIONS[idx]
        assert FUNCTIONS[idx] in calls


def test_fail_closed_rbac_precedes_lazy_navigation_and_no_eager_tabs():
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    page = next(n for n in tree.body
                if isinstance(n, ast.FunctionDef)
                and n.name == "_show_dashboards_page_impl")
    guards = [(idx, node) for idx, node in enumerate(page.body)
              if isinstance(node, ast.If) and isinstance(node.test, ast.UnaryOp)
              and isinstance(node.test.op, ast.Not)
              and isinstance(node.test.operand, ast.Name)
              and node.test.operand.id == "can_read"]
    assert len(guards) == 1
    idx, deny = guards[0]
    assert any(isinstance(n, ast.Return) for n in deny.body)
    assert any(isinstance(n, ast.Call)
               and isinstance(n.func, ast.Name)
               and n.func.id == "has_permission"
               for stmt in page.body[:idx] for n in ast.walk(stmt))
    selectors = [(i, n) for i, n in enumerate(page.body)
                 if isinstance(n, ast.Assign)
                 and isinstance(n.value, ast.Call)
                 and isinstance(n.value.func, ast.Attribute)
                 and n.value.func.attr == "selectbox"]
    assert len(selectors) == 1 and idx < selectors[0][0]
    assert not any(isinstance(n, ast.Call)
                   and isinstance(n.func, ast.Attribute)
                   and n.func.attr == "tabs"
                   for n in ast.walk(page))


def test_kpi_calculations_only_occur_inside_a_selected_panel():
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    page = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                and n.name == "_show_dashboards_page_impl")
    panels = [node for node in page.body if _panel_index(node) is not None]

    def calls(node):
        return [n for n in ast.walk(node) if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name) and n.func.id in FUNCTIONS]

    for panel in panels:
        assert len(calls(panel)) == 1, "Une vue calcule exactement ses propres KPI"
    for stmt in page.body:
        if _panel_index(stmt) is None:
            assert not calls(stmt), "KPI lancé sans sélection explicite de panneau"


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
