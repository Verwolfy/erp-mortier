"""Composant d'impression de rapports de gestion : données autorisées en entrée."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest


@pytest.fixture
def ui(monkeypatch):
    st = MagicMock()
    st.session_state = {}
    cols = [MagicMock(), MagicMock(), MagicMock()]
    for c in cols:
        c.button.return_value = False
    st.columns.return_value = cols
    monkeypatch.setitem(sys.modules, "streamlit", st)
    source = Path(__file__).resolve().parents[1] / "modules/documents/report_actions.py"
    spec = importlib.util.spec_from_file_location("report_actions_checked", source)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, st, cols


def test_empty_report_creates_no_pdf(ui):
    mod, st, cols = ui
    mod.show_report_actions(
        pd.DataFrame(columns=["article", "entrees"]),
        columns=["article", "entrees"], title="MP",
        period="2026-11-01 au 2026-11-23", scope="empty",
    )
    st.columns.assert_not_called()
    st.info.assert_called_once()


def test_regular_report_has_consulter_imprimer_pdf(ui):
    mod, st, cols = ui
    frame = pd.DataFrame([{"article": "MP-1", "entrees": 12}])
    mod.show_report_actions(
        frame, columns=["article", "entrees"], title="MP",
        period="2026-11-01 au 2026-11-23", scope="mp",
    )
    assert cols[0].button.call_args.args[0] == "👁️ Consulter"
    assert cols[1].button.call_args.args[0] == "🖨️ Imprimer"
    assert cols[2].download_button.call_count == 1
    assert cols[2].download_button.call_args.args[1].startswith(b"%PDF")
    st.dataframe.assert_called_once()
    assert "erp_report_action_mp" not in st.session_state


def test_print_report_only_after_click(ui):
    mod, st, cols = ui
    cols[1].button.return_value = True
    frame = pd.DataFrame([{"article": "MP-1", "entrees": 12}])
    mod.show_report_actions(
        frame, columns=["article", "entrees"], title="MP",
        period="2026-11-01 au 2026-11-23", scope="mp",
    )
    assert st.session_state["erp_report_action_mp"] == "imprimer"
    st.pdf.assert_called_once()
    st.warning.assert_called_once()


def test_pdf_limit_does_not_block_other_exports(ui):
    mod, st, cols = ui
    frame = pd.DataFrame([{"article": f"MP-{i}", "entrees": i}
                          for i in range(251)])
    mod.show_report_actions(
        frame, columns=["article", "entrees"], title="MP",
        period="2026-11-01 au 2026-11-23", scope="mp",
    )
    cols[2].download_button.assert_not_called()
    cols[2].button.assert_called_once()
    assert cols[2].button.call_args.kwargs["disabled"] is True
    st.dataframe.assert_called_once()


def test_missing_column_fails_before_export(ui):
    mod, st, cols = ui
    with pytest.raises(ValueError):
        mod.show_report_actions(
            pd.DataFrame([{"article": "MP-1"}]),
            columns=["article", "quantite"], title="MP",
            period="2026-11", scope="mp",
        )
    st.columns.assert_not_called()
