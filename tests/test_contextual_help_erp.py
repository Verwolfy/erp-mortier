"""Tests sans réseau : aides contextuelles Streamlit et couverture des rubriques."""
from __future__ import annotations

import ast
import importlib.util
from contextlib import contextmanager
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "modules/help/contextual.py"
spec = importlib.util.spec_from_file_location("_erp_contextual_help", MODULE)
help_ui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(help_ui)


class FakeStreamlit:
    def __init__(self):
        self.popovers = []
        self.elements = []

    @contextmanager
    def popover(self, title, *, help=None):
        self.popovers.append((title, help))
        yield self

    def markdown(self, text):
        self.elements.append(text)


def test_all_topics_are_complete_and_unique():
    assert len(help_ui.TOPICS) >= 65
    for key, topic in help_ui.TOPICS.items():
        assert key and len(topic) == 4
        assert isinstance(topic[0], str) and len(topic[0].strip()) >= 3
        assert all(isinstance(text, str) and len(text.strip()) >= 16 for text in topic[1:])
        assert "clé service_role" not in " ".join(topic).casefold()


def test_click_open_and_hover_show_explanations_without_network():
    st = FakeStreamlit()
    help_ui.show_context_help(st, "production.historique")
    assert len(st.popovers) == 1
    assert "Consommations" in st.popovers[0][0]
    assert "survol" not in st.popovers[0][1].lower()
    assert len(st.elements) == 3
    assert st.elements[0].startswith("**Notion**")
    assert st.elements[1].startswith("**Comment faire**")
    assert st.elements[2].startswith("**À vérifier**")
    assert "Chargement manuel" in " ".join(st.elements)


def test_help_specific_to_history_and_irreversible_actions():
    page = help_ui.field_help("Page des historiques Production", module="production")
    assert "page" in page.casefold() and "aucune opération" in page
    operation = help_ui.field_help("Valider et clôturer cet OF", module="production")
    assert "effet durable" in operation
    assert "base" in operation
    assert "mot de passe" in help_ui.field_help("Mot de passe").lower()


@pytest.mark.parametrize("topic", [
    "admin.clients", "achats.reception", "stocks.entree", "production.recettes",
    "production.of", "production.cq", "production.historique",
    "production.couts", "ventes.facture", "crm.pipeline", "finance.scf",
    "rh.pae", "dashboard.pnl", "documents.edition", "help.guide",
])
def test_representative_business_topics_present(topic):
    assert topic in help_ui.TOPICS
    hover = help_ui.topic_help(topic)
    assert len(hover) > 20 and "Ouvrir" in hover


def test_all_ui_topic_references_exist_and_forms_are_not_replaced():
    paths = [
        ROOT / "app.py",
        ROOT / "modules/help/views.py",
        ROOT / "modules/production/cost_views.py",
    ] + list((ROOT / "modules").glob("*/views.py"))
    topic_calls = 0
    input_tips = 0
    seen = set()
    for path in set(paths):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id in {"show_context_help", "topic_help"}:
                assert node.args
                keyarg = node.args[-1]
                assert isinstance(keyarg, ast.Constant) and isinstance(keyarg.value, str)
                assert keyarg.value in help_ui.TOPICS, (path, keyarg.value)
                if node.func.id == "show_context_help":
                    topic_calls += 1
                    seen.add(keyarg.value)
            if node.func.id == "field_help":
                input_tips += 1
    assert topic_calls >= 55
    assert input_tips >= 220
    assert len(seen) >= 60


def test_missing_topic_or_empty_field_cannot_silently_show_wrong_help():
    with pytest.raises(KeyError):
        help_ui.show_context_help(FakeStreamlit(), "unknown.topic")
    with pytest.raises(ValueError):
        help_ui.field_help(" ")
