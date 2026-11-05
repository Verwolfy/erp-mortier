"""Règle de dates du tableau de bord P&L et absence de prorata implicite."""
import datetime
from pathlib import Path
import ast

VIEWS = Path(__file__).resolve().parents[1] / "modules" / "dashboards" / "views.py"


def _month_end_function():
    """Exécuter uniquement la fonction pure extraite de l'AST des vues."""
    source = VIEWS.read_text(encoding="utf-8")
    tree = ast.parse(source)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
              and n.name == "_current_month_end")
    # Astreindre le test à la définition réelle ; les autres vues ne sont pas exécutées.
    mod = ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[]))
    scope = {"datetime": datetime}
    exec(compile(mod, str(VIEWS), "exec"), scope)
    return scope["_current_month_end"]


def test_month_end_for_regular_leap_and_year_boundary():
    fn = _month_end_function()
    assert fn(datetime.date(2026, 11, 5)) == datetime.date(2026, 11, 30)
    assert fn(datetime.date(2026, 12, 31)) == datetime.date(2026, 12, 31)
    assert fn(datetime.date(2024, 2, 1)) == datetime.date(2024, 2, 29)
    assert fn(datetime.date(2026, 2, 1)) == datetime.date(2026, 2, 28)


def test_pnl_date_widget_uses_full_month_end():
    source = VIEWS.read_text(encoding="utf-8")
    assert 'date_fin_pnl = c_fin_pnl.date_input(' in source
    assert '_current_month_end(datetime.date.today()), key="f_pnl"' in source
    assert 'date_deb_pnl = c_deb_pnl.date_input(' in source
