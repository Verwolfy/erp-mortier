"""RH : aucune mutation sur des droits d'écriture rendus obsolètes."""
from pathlib import Path

SRC=(Path(__file__).resolve().parents[1]/"modules"/"rh"/"views.py").read_text(encoding="utf-8")


def test_creation_employe_revalide_au_clic():
    branch=SRC.split('if st.form_submit_button("Enregistrer"',1)[1].split("with tab2:",1)[0]
    assert branch.index("fresh = _rh_access()") < branch.index("create_employe(")
    assert "fresh[1] is not True" in branch
    assert "fresh[0] != user_role" in branch
    assert "Droit RH écriture absent ou révoqué" in branch


def test_creation_conge_revalide_au_clic():
    branch=SRC.split('if st.form_submit_button("Soumettre la demande"',1)[1].split("if can_read_paie:",1)[0]
    assert branch.index("fresh = _rh_access()") < branch.index("create_demande_conge(")
    assert "fresh[1] is not True" in branch
    assert "fresh[0] != user_role" in branch
    assert "Droit RH écriture absent ou révoqué" in branch


def test_paie_revalide_egalement():
    branch=SRC.split('"Simuler IRG"',1)[1]
    assert "fresh = _rh_access()" in branch
    assert "fresh[2] is not True" in branch
