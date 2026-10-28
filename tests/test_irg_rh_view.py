"""Vérification statique : l'accès Paie ne doit pas hériter d'un simple accès RH."""
from pathlib import Path
import ast

SRC=Path(__file__).resolve().parents[1]/"modules"/"rh"/"views.py"
TEXT=SRC.read_text(encoding="utf-8")
TREE=ast.parse(TEXT)


def test_paies_separees_des_conges():
    assert 'has_permission(user_role, "Paie", "lecture")' in TEXT
    assert 'if can_read_paie:' in TEXT
    assert "simuler_irg_depuis_supabase" in TEXT


def test_pas_de_bulletin_ou_ecriture_dans_onglet():
    assert "insert_hybrid" not in TEXT
    assert "create_fiche_paie" not in TEXT
    assert "st.metric" in TEXT


def test_callbacks_activite_rh_conserves():
    calls=[n for n in ast.walk(TREE)
        if isinstance(n,ast.Call)
        and isinstance(n.func,ast.Attribute)
        and n.func.attr=="form_submit_button"]
    assert len(calls)==2
