"""Garde de droits RH/Paie relue depuis la base, sans réseau."""
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest


SOURCE=Path(__file__).resolve().parents[1]/"modules"/"rh"/"views.py"


@pytest.fixture
def setup(monkeypatch):
    st=types.ModuleType("streamlit")
    st.title=MagicMock()
    st.subheader=MagicMock()
    st.caption=MagicMock()
    st.error=MagicMock()
    st.session_state={
        "authenticated": True,
        "user": {"user_id": "USER-1", "role": "ADMIN"},
    }
    client=MagicMock()
    query=client.table.return_value.select.return_value.eq.return_value.limit.return_value
    query.execute.return_value=types.SimpleNamespace(
        data=[{"user_id":"USER-1","role":"COMPTABLE","actif":"OUI"}]
    )
    db=types.ModuleType("core.db_service")
    db.get_supabase_client=MagicMock(return_value=client)
    roles=types.ModuleType("config.roles")
    roles.has_permission=MagicMock(side_effect=lambda role,module,perm: (
        role,module,perm) in {
            ("COMPTABLE","RH","lecture"),
            ("RH","RH","lecture"),
            ("RH","RH","ecriture"),
            ("RH","Paie","lecture"),
        })
    service=types.ModuleType("modules.rh.service")
    for method in ("create_employe","create_demande_conge","get_employes","get_conges"):
        setattr(service,method,MagicMock())
    for key,val in {
        "streamlit":st, "config":types.ModuleType("config"),
        "config.roles":roles, "core":types.ModuleType("core"),
        "core.db_service":db, "modules":types.ModuleType("modules"),
        "modules.rh":types.ModuleType("modules.rh"),
        "modules.rh.service":service,
    }.items():
        monkeypatch.setitem(sys.modules,key,val)
    spec=importlib.util.spec_from_file_location("rh_views_fresh_test",SOURCE)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return types.SimpleNamespace(
        mod=mod,st=st,roles=roles,db=db,client=client,query=query,service=service,
    )


def test_role_administrateur_session_n_accorde_pas_paie(setup):
    assert setup.mod._rh_access()==("COMPTABLE",False,False)
    assert all(args.args[0] == "COMPTABLE"
               for args in setup.roles.has_permission.call_args_list)


def test_role_reel_serveur_active_paie(setup):
    setup.query.execute.return_value.data=[
        {"user_id":"USER-1","role":"RH","actif":"OUI"}
    ]
    assert setup.mod._rh_access()==("RH",True,True)


@pytest.mark.parametrize("actor",[
    [], [{"user_id":"USER-2","role":"RH","actif":"OUI"}],
    [{"user_id":"USER-1","role":"RH","actif":"NON"}],
    [{"user_id":"USER-1","role":"RH","actif":"OUI"}]*2,
    [{"user_id":"USER-1","role":None,"actif":"OUI"}],
])
def test_compte_invalide_refuse(setup,actor):
    setup.query.execute.return_value.data=actor
    assert setup.mod._rh_access() is None
    setup.mod.show_rh_page()
    setup.service.get_employes.assert_not_called()
    setup.st.error.assert_called()


def test_refus_session_anonyme(setup):
    setup.st.session_state["authenticated"]=False
    assert setup.mod._rh_access() is None
    setup.db.get_supabase_client.assert_not_called()


def test_refus_reseau_indisponible(setup):
    setup.query.execute.side_effect=TimeoutError("private")
    assert setup.mod._rh_access() is None
    setup.mod.show_rh_page()
    setup.service.get_employes.assert_not_called()


def test_absence_permission_rh_bloque_tous_acces(setup):
    setup.roles.has_permission.return_value=False
    setup.roles.has_permission.side_effect=None
    assert setup.mod._rh_access() is None
    setup.mod.show_rh_page()
    setup.service.get_employes.assert_not_called()


def test_nouvelle_verification_avant_calcul_irg():
    source=SOURCE.read_text(encoding="utf-8")
    assert "fresh = _rh_access()" in source
    assert "fresh[2] is not True" in source
    assert "simuler_irg_depuis_supabase" in source


def test_preflight_paie_aucune_lecture_sans_clic(setup, monkeypatch):
    from datetime import date
    stub_utils=types.ModuleType("core.utils")
    stub_utils.get_local_now=MagicMock(return_value=types.SimpleNamespace(
        date=lambda: date(2026,10,29)
    ))
    monkeypatch.setitem(sys.modules,"core.utils",stub_utils)
    setup.st.date_input=MagicMock(return_value=date(2026,10,29))
    setup.st.button=MagicMock(return_value=False)
    setup.mod._preflight_paie_tab("RH")
    setup.db.get_supabase_client.assert_not_called()


def test_preflight_paie_droit_revoque_bloque_lecture(setup, monkeypatch):
    from datetime import date
    stub_utils=types.ModuleType("core.utils")
    stub_utils.get_local_now=MagicMock(return_value=types.SimpleNamespace(
        date=lambda: date(2026,10,29)
    ))
    monkeypatch.setitem(sys.modules,"core.utils",stub_utils)
    setup.st.date_input=MagicMock(return_value=date(2026,10,29))
    setup.st.button=MagicMock(return_value=True)
    setup.mod._rh_access=MagicMock(return_value=None)
    setup.mod._preflight_paie_tab("RH")
    setup.db.get_supabase_client.assert_not_called()
    setup.st.error.assert_called()


def test_preflight_paie_documente_sans_bulletin(setup, monkeypatch):
    from datetime import date
    stub_utils=types.ModuleType("core.utils")
    stub_utils.get_local_now=MagicMock(return_value=types.SimpleNamespace(
        date=lambda: date(2026,10,29)
    ))
    monkeypatch.setitem(sys.modules,"core.utils",stub_utils)
    stub_paie=types.ModuleType("core.preflight_paie")
    stub_paie.PreparationPaieIndisponible=ValueError
    stub_paie.lire_preparation_paie=MagicMock(return_value={
        "reference_cnas_salarie":False,
        "reference_cnas_employeur":False,
        "reference_irg_mensuel":False,
    })
    monkeypatch.setitem(sys.modules,"core.preflight_paie",stub_paie)
    setup.st.date_input=MagicMock(return_value=date(2026,10,29))
    setup.st.button=MagicMock(return_value=True)
    setup.st.metric=MagicMock()
    setup.st.warning=MagicMock()
    setup.mod._rh_access=MagicMock(return_value=("RH",True,True))
    setup.mod._preflight_paie_tab("RH")
    assert setup.st.metric.call_count==3
    stub_paie.lire_preparation_paie.assert_called_once()
    assert "bulletin" in setup.st.warning.call_args.args[0]
