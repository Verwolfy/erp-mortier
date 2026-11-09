"""ERP-050 : parcours authentifiés simulés, sans identifiant ni réseau réel.

Récupère les fixtures de vues existantes qui importent le vrai code UI avec
Streamlit et les services doublés. Le SQL live a ses preuves indépendantes.
"""
from __future__ import annotations

import pytest

from tests.test_achats_views_security import ui as achats_ui
from tests.test_app_security import env as auth_env


def test_erp049_fournisseur_sim_inactif_non_propose_dans_achat(achats_ui):
    achats_ui.db.fetch_data.return_value = [
        {"fournisseur_id": "SIM-ERP49-FOUR-LIANTS", "nom": "SIMULATION", "actif": "NON"},
        {"fournisseur_id": "SIM-ERP50-ACTIF-FICTIF", "nom": "ACTIF DE TEST", "actif": "OUI"},
    ]
    offres = achats_ui.mod.get_fournisseurs_actifs()
    assert offres["fournisseur_id"].tolist() == ["SIM-ERP50-ACTIF-FICTIF"]
    achats_ui.db.fetch_data.assert_called_once_with("fournisseurs")
    achats_ui.achats.create_commande_achat.assert_not_called()


def test_erp049_matiere_sim_inactive_non_proposee_dans_achat(achats_ui):
    achats_ui.db.fetch_data.return_value = [
        {"mp_id": "SIM-ERP49-MP-CIMENT", "nom": "SIMULATION", "actif": "NON"},
        {"mp_id": "SIM-ERP50-ACTIVE", "nom": "ACTIVE DE TEST", "actif": "OUI"},
    ]
    matieres = achats_ui.mod.get_mp_actives()
    assert matieres["mp_id"].tolist() == ["SIM-ERP50-ACTIVE"]
    achats_ui.db.fetch_data.assert_called_once_with("matieres_premieres")
    achats_ui.achats.create_commande_achat.assert_not_called()


@pytest.mark.parametrize("lecteur,table", [
    ("get_fournisseurs_actifs", "fournisseurs"),
    ("get_mp_actives", "matieres_premieres"),
])
def test_referentiel_actif_manquant_refuse_au_lieu_de_tout_montrer(achats_ui, lecteur, table):
    achats_ui.db.fetch_data.return_value = [{"identifiant": "SIM-ERP49"}]
    with pytest.raises(achats_ui.strict.DataReadError, match="incomplet"):
        getattr(achats_ui.mod, lecteur)()
    achats_ui.db.fetch_data.assert_called_once_with(table)
    achats_ui.achats.create_commande_achat.assert_not_called()


def test_session_fictive_inactive_ne_devient_pas_admin(auth_env):
    auth_env.st.session_state["user"] = {
        "user_id": "SIM-ERP49-EMP-COM", "role": "ADMIN", "nom": "SIMULATION"
    }
    auth_env.client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"user_id": "SIM-ERP49-EMP-COM", "role": "ADMIN",
         "nom": "SIMULATION", "actif": "NON"}
    ]
    assert auth_env.app._verified_user(1000) is None
    auth_env.auth.logout.assert_called_once()
    auth_env.roles.get_allowed_modules.assert_not_called()
    auth_env.roles.has_permission.assert_not_called()
