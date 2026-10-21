"""Tests isolés de l'écran Production : aucun appel réel à Supabase."""
from __future__ import annotations

import importlib.util
import sys
import types
from copy import deepcopy
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

VIEW_PATH = Path(__file__).resolve().parents[1] / 'modules' / 'production' / 'views.py'


@pytest.fixture
def ui(monkeypatch):
    st = MagicMock()
    st.session_state = {'authenticated': True, 'user': {'user_id': 'USR-1', 'role': 'ADMIN'}}
    st.tabs.side_effect = lambda x: [MagicMock() for _ in x]
    st.form_submit_button.return_value = False
    st.button.return_value = False
    st.checkbox.return_value = False
    st.selectbox.side_effect = lambda label, options, **kw: list(options)[0]
    st.number_input.return_value = 10.0
    st.radio.return_value = 'OUI'
    st.date_input.return_value = '2026-10-21'
    st.text_input.return_value = 'Contrôleur 1'
    st.text_area.return_value = 'RAS'

    client = MagicMock()
    query = client.table.return_value.select.return_value.eq.return_value.limit.return_value
    query.execute.return_value = types.SimpleNamespace(
        data=[{'user_id': 'USR-1', 'role': 'FABRICANT', 'actif': 'OUI'}])
    db = types.ModuleType('core.db_service')
    db.get_supabase_client = MagicMock(return_value=client)
    db.fetch_data = MagicMock(return_value=[])
    roles = types.ModuleType('config.roles')
    roles.has_permission = MagicMock(return_value=True)
    utils = types.ModuleType('core.utils')
    utils.get_local_now = MagicMock(return_value='2026-10-21')
    production = types.ModuleType('modules.production.service')
    for name in ('create_recette', 'create_ordre_fabrication', 'get_recettes',
                 'get_ordres_fabrication', 'changer_statut_of', 'enregistrer_controle_qualite',
                 'get_lignes_recette',
                 'get_consommations_of', 'get_controles_qualite'):
        setattr(production, name, MagicMock())
    production.create_recette.return_value = 'REC-0001'
    production.create_ordre_fabrication.return_value = 'OF-0001'
    production.changer_statut_of.return_value = {'of_id': 'OF-0001', 'statut': 'EN_COURS'}
    production.enregistrer_controle_qualite.return_value = {'of_id': 'OF-0001', 'statut': 'TERMINE'}
    production.get_lignes_recette.return_value = pd.DataFrame([
        {'mp_id': 'MP-1', 'quantite_par_unite': .25}])
    for name in ('get_recettes', 'get_ordres_fabrication', 'get_consommations_of',
                 'get_controles_qualite'):
        getattr(production, name).return_value = pd.DataFrame()
    modules = types.ModuleType('modules')
    for key, value in {
        'streamlit': st, 'config': types.ModuleType('config'), 'config.roles': roles,
        'core': types.ModuleType('core'), 'core.db_service': db, 'core.utils': utils,
        'modules': modules, 'modules.production': types.ModuleType('modules.production'),
        'modules.production.service': production,
    }.items():
        monkeypatch.setitem(sys.modules, key, value)
    spec = importlib.util.spec_from_file_location('production_views_under_test', VIEW_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return types.SimpleNamespace(mod=mod, st=st, client=client, query=query,
                                 db=db, roles=roles, prod=production)


def _products():
    return pd.DataFrame([{'pf_id': 'PF-1', 'nom': 'Peinture', 'unite_production': 'Kg', 'actif': 'OUI'}])


def _skus(factor=1, unit='Kg', pack=''):
    return pd.DataFrame([{'sku_id': 'SKU-1', 'pf_id': 'PF-1', 'format': 'test',
                          'unite_vente': unit, 'facteur_conversion': factor,
                          'emballage_mp_id': pack, 'actif': 'OUI'}])


def _materials():
    return pd.DataFrame([{'mp_id': 'MP-1', 'nom': 'Ciment', 'unite_stock': 'Kg',
                          'categorie_mp': 'LIANT', 'actif': 'OUI'}])


def _orders(status='EN_COURS'):
    return pd.DataFrame([{'of_id': 'OF-0001', 'pf_id': 'PF-1', 'sku_id': 'SKU-1',
                          'recette_id': 'REC-0001', 'statut': status,
                          'quantite_prevue': 100, 'date_planification': '2026-10-21'}])


def _closure(conforme='OUI', qty=100., pack_id=None, pack_qty=0.):
    return {'of_id': 'OF-0001', 'conforme': conforme, 'remarques': 'RAS',
            'controleur': 'Responsable Q', 'quantite_produite': qty,
            'emballage_mp_id': pack_id, 'emballage_consomme': pack_qty}


@pytest.mark.parametrize('auth,user', [
    (False, {'user_id': 'USR-1'}), (True, None), (True, {}),
    (True, {'user_id': ''}), (True, {'user_id': 1}),
])
def test_auth_failure_never_reads_business_data(ui, auth, user):
    ui.st.session_state = {'authenticated': auth, 'user': user}
    ui.mod.show_production_page()
    ui.db.fetch_data.assert_not_called()
    ui.prod.get_recettes.assert_not_called()
    ui.st.tabs.assert_not_called()


@pytest.mark.parametrize('records', [
    [], [{'user_id': 'USR-2', 'role': 'FABRICANT', 'actif': 'OUI'}],
    [{'user_id': 'USR-1', 'role': 'FABRICANT', 'actif': 'NON'}],
    [{'user_id': 'USR-1', 'role': '', 'actif': 'OUI'}],
    [{'user_id': 'USR-1', 'role': 'FABRICANT', 'actif': 'OUI'}]*2,
])
def test_invalid_db_accounts_block(ui, records):
    ui.query.execute.return_value = types.SimpleNamespace(data=records)
    ui.mod.show_production_page()
    ui.db.fetch_data.assert_not_called()
    ui.st.tabs.assert_not_called()


def test_backend_error_denies_access(ui):
    ui.query.execute.side_effect = RuntimeError('SQL down')
    ui.mod.show_production_page()
    ui.st.tabs.assert_not_called()
    ui.db.fetch_data.assert_not_called()


def test_stale_session_admin_does_not_bypass_db_role(ui):
    ui.roles.has_permission.return_value = False
    ui.mod.show_production_page()
    ui.roles.has_permission.assert_called_once_with('FABRICANT', 'Production', 'lecture')
    ui.db.fetch_data.assert_not_called()


def test_read_only_user_sees_history_without_mutations(ui):
    ui.roles.has_permission.side_effect = lambda role, module, perm: perm == 'lecture'
    ui.mod.show_production_page()
    ui.prod.create_recette.assert_not_called()
    ui.prod.create_ordre_fabrication.assert_not_called()
    ui.prod.enregistrer_controle_qualite.assert_not_called()
    ui.st.form.assert_not_called()


def test_access_reads_live_role_and_checks_stocks(ui):
    assert ui.mod._production_access() == ('USR-1', True, True)
    assert ui.roles.has_permission.call_args_list[0].args == ('FABRICANT', 'Production', 'lecture')
    assert ui.roles.has_permission.call_args_list[2].args == ('FABRICANT', 'Stocks', 'ecriture')


@pytest.mark.parametrize('batch,qty,expected', [(1000, 250, 0.25), (20, 3, 0.15), (100, 100, 1.0)])
def test_recipe_batch_is_converted_to_per_unit(ui, batch, qty, expected):
    assert ui.mod._line_per_unit(qty, batch) == expected


@pytest.mark.parametrize('qty,yield_qty', [
    (0, 1000), (-1, 1000), (100, 0), (float('nan'), 10),
    (float('inf'), 100), (1, float('nan')), (True, 100),
])
def test_invalid_recipe_quantities_are_rejected(ui, qty, yield_qty):
    with pytest.raises(ValueError):
        ui.mod._line_per_unit(qty, yield_qty)


def test_recipe_quantity_below_precision_limit_blocks(ui):
    with pytest.raises(ValueError):
        ui.mod._line_per_unit('0.00000001', '100000000000')


@pytest.mark.parametrize('factor,unit,compatible', [
    (1, 'Kg', True), (1.0, 'kg', True), (25, 'Kg', False),
    (1, 'Sac', False), (None, 'Kg', False), (-1, 'Kg', False),
])
def test_sku_conversion_is_fail_closed(ui, factor, unit, compatible):
    sku = _skus(factor, unit).iloc[0]
    assert ui.mod._sku_unit_safe(sku, _products()) is compatible


def test_unsupported_sku_cannot_create_of(ui):
    ui.prod.get_recettes.return_value = pd.DataFrame([{
        'recette_id': 'REC-0001', 'pf_id': 'PF-1', 'version': 'v1',
        'actif': 'OUI', 'rendement_unite': 1000}])
    ui.mod._of_tab('USR-1', True, _products(), _skus(25, 'Sac'))
    ui.prod.create_ordre_fabrication.assert_not_called()
    ui.st.form.assert_not_called()
    ui.st.error.assert_called()


def test_non_idempotent_recipe_creation_unconfirmed_not_retried(ui):
    payload = {'pf_id': 'PF-1', 'version': 'v1', 'rendement_unite': 1000,
               'instructions': 'RAS', 'panier_lignes': [{'mp_id': 'MP-1', 'quantite_par_unite': .5}]}
    ui.prod.create_recette.side_effect = RuntimeError('network timeout')
    ui.mod._create_document('recette', 'USR-1', payload)
    key = ui.mod._document_key('recette', 'USR-1')
    assert ui.st.session_state[key]['status'] == 'uncertain'
    ui.st.button.return_value = True
    ui.mod._document_panel('recette', 'USR-1')
    ui.prod.create_recette.assert_called_once()
    assert key in ui.st.session_state
    ui.mod._create_document('recette', 'USR-1', payload)
    ui.prod.create_recette.assert_called_once()


def test_non_idempotent_of_creation_is_not_retried(ui):
    payload = {'pf_id': 'PF-1', 'recette_id': 'REC-0001', 'sku_id': 'SKU-1',
               'quantite_prevue': 100, 'date_planification': '2026-10-21', 'notes': ''}
    ui.prod.create_ordre_fabrication.side_effect = RuntimeError('lost connection')
    ui.mod._create_document('of', 'USR-1', payload)
    assert ui.st.session_state[ui.mod._document_key('of', 'USR-1')]['status'] == 'uncertain'
    ui.mod._create_document('of', 'USR-1', payload)
    ui.prod.create_ordre_fabrication.assert_called_once()


def test_created_recipe_confirmation_clears_only_own_cart(ui):
    payload = {'pf_id': 'PF-1', 'version': 'v1', 'rendement_unite': 1000,
               'instructions': 'ok', 'panier_lignes': [{'mp_id': 'MP-1', 'quantite_par_unite': .2}]}
    ui.st.session_state[ui.mod._cart_key('USR-1')] = {'pf_id': 'PF-1', 'yield': '1000', 'lines': [payload]}
    ui.st.session_state[ui.mod._cart_key('USR-2')] = {'pf_id': 'PF-2', 'yield': '1000', 'lines': [payload]}
    ui.mod._create_document('recette', 'USR-1', payload)
    key = ui.mod._document_key('recette', 'USR-1')
    assert ui.st.session_state[key]['status'] == 'confirmed'
    assert ui.mod._cart_key('USR-1') not in ui.st.session_state
    assert ui.mod._cart_key('USR-2') in ui.st.session_state
    ui.prod.create_recette.assert_called_once_with(**payload)


def test_cart_resets_if_product_or_yield_changes(ui):
    key = ui.mod._cart_key('USR-1')
    ui.st.session_state[key] = {'pf_id': 'PF-2', 'yield': '10', 'lines': [
        {'mp_id': 'MP-1', 'nom_mp': 'Ciment', 'unite_stock': 'Kg', 'quantite_batch': 100}]}
    ui.mod._recipe_tab('USR-1', True, _products(), _materials())
    assert ui.st.session_state[key]['pf_id'] == 'PF-1'
    assert ui.st.session_state[key]['lines'] == []


def test_recipe_conversion_payload_saved_per_unit(ui):
    key = ui.mod._cart_key('USR-1')
    ui.st.number_input.side_effect = [1000.0, 2.0]
    ui.st.checkbox.return_value = True
    ui.st.button.side_effect = lambda name, **kw: name == 'Sauvegarder la recette'
    ui.st.session_state[key] = {'pf_id': 'PF-1', 'yield': '1000.0', 'lines': [
        {'mp_id': 'MP-1', 'nom_mp': 'Ciment', 'unite_stock': 'Kg', 'quantite_batch': 300.0}]}
    ui.mod._recipe_tab('USR-1', True, _products(), _materials())
    kwargs = ui.prod.create_recette.call_args.kwargs
    assert kwargs['panier_lignes'] == [{'mp_id': 'MP-1', 'quantite_par_unite': .3}]
    assert kwargs['rendement_unite'] == 1000.0


def test_close_replays_identical_payload_after_unknown_commit(ui):
    payload = _closure()
    first = {'n': 0}
    def close(**kwargs):
        first['n'] += 1
        if first['n'] == 1:
            raise RuntimeError('connection lost after commit')
        return {'of_id': 'OF-0001', 'statut': 'TERMINE'}
    ui.prod.enregistrer_controle_qualite.side_effect = close
    ui.mod._start_closure('USR-1', payload, True)
    key = ui.mod._closure_key('USR-1')
    assert ui.st.session_state[key]['status'] == 'uncertain'
    first_call = deepcopy(ui.prod.enregistrer_controle_qualite.call_args.kwargs)
    payload['quantite_produite'] = 99999
    ui.st.button.return_value = True
    ui.mod._closure_panel('USR-1', True)
    assert ui.prod.enregistrer_controle_qualite.call_count == 2
    assert ui.prod.enregistrer_controle_qualite.call_args.kwargs == first_call
    assert ui.st.session_state[key]['status'] == 'confirmed'
    ui.mod._start_closure('USR-1', _closure(qty=200), True)
    assert ui.prod.enregistrer_controle_qualite.call_count == 2


def test_pending_close_no_auto_retry(ui):
    key = ui.mod._closure_key('USR-1')
    ui.st.session_state[key] = {'status': 'uncertain', 'payload': _closure()}
    ui.mod._closure_panel('USR-1', True)
    ui.prod.enregistrer_controle_qualite.assert_not_called()


def test_no_stock_rights_prevents_confirmed_close(ui):
    ui.mod._start_closure('USR-1', _closure(), False)
    ui.prod.enregistrer_controle_qualite.assert_not_called()
    assert ui.st.session_state[ui.mod._closure_key('USR-1')]['status'] == 'uncertain'


def test_rejected_close_needs_no_stock_rights(ui):
    ui.prod.enregistrer_controle_qualite.return_value = {'of_id': 'OF-0001', 'statut': 'REJETE'}
    ui.mod._start_closure('USR-1', _closure('NON', 0), False)
    ui.prod.enregistrer_controle_qualite.assert_called_once()


def test_pre_rpc_validation_error_unfreezes_close_form(ui):
    ui.prod.enregistrer_controle_qualite.side_effect = ValueError('invalid number')
    ui.mod._start_closure('USR-1', _closure(), True)
    assert ui.mod._closure_key('USR-1') not in ui.st.session_state


def test_unknown_reply_requires_manual_verification(ui):
    ui.prod.enregistrer_controle_qualite.return_value = {'unexpected': True}
    ui.mod._start_closure('USR-1', _closure(), True)
    assert ui.st.session_state[ui.mod._closure_key('USR-1')]['status'] == 'uncertain'


def test_user_pending_close_is_isolated(ui):
    ui.st.session_state[ui.mod._closure_key('USR-1')] = {'status': 'uncertain', 'payload': _closure()}
    ui.mod._closure_panel('USR-2', True)
    ui.prod.enregistrer_controle_qualite.assert_not_called()


def test_legacy_quality_status_not_sent_to_unavailable_transition(ui):
    ui.prod.get_ordres_fabrication.return_value = _orders('CONTROLE_QUALITE')
    ui.mod._followup_tab('USR-1', True, True, _skus(), _materials(), _products())
    ui.prod.changer_statut_of.assert_not_called()
    ui.prod.enregistrer_controle_qualite.assert_not_called()
    ui.st.error.assert_called()


def test_en_cours_status_goes_directly_to_quality(ui):
    ui.prod.get_ordres_fabrication.return_value = _orders('EN_COURS')
    ui.mod._control_form = MagicMock()
    ui.mod._followup_tab('USR-1', True, True, _skus(), _materials(), _products())
    ui.mod._control_form.assert_called_once()
    ui.prod.changer_statut_of.assert_not_called()


def test_quality_form_blocks_unsupported_sku(ui):
    ui.mod._control_form('USR-1', _orders().iloc[0], _skus(25, 'Sac'), _materials(), _products(), True)
    ui.st.form.assert_not_called()
    ui.prod.enregistrer_controle_qualite.assert_not_called()
    ui.st.error.assert_called()


def test_quality_form_requires_explicit_recipe_ack(ui):
    ui.mod._control_form('USR-1', _orders().iloc[0], _skus(), _materials(), _products(), True)
    assert ui.st.form_submit_button.call_args.kwargs['disabled'] is True
    ui.prod.enregistrer_controle_qualite.assert_not_called()


def test_quality_rejection_has_zero_qty_packaging(ui):
    ui.st.radio.return_value = 'NON'
    ui.st.form_submit_button.return_value = True
    ui.prod.enregistrer_controle_qualite.return_value = {'of_id': 'OF-0001', 'statut': 'REJETE'}
    ui.mod._control_form('USR-1', _orders().iloc[0], _skus(1, 'Kg', 'EMB-1'), _materials(), _products(), False)
    kwargs = ui.prod.enregistrer_controle_qualite.call_args.kwargs
    assert kwargs['quantite_produite'] == 0
    assert kwargs['emballage_mp_id'] is None
    assert kwargs['emballage_consomme'] == 0


def test_quality_form_does_not_default_packaging_to_produced_qty(ui):
    ui.st.form_submit_button.return_value = True
    ui.st.checkbox.return_value = True
    ui.st.number_input.side_effect = [100., 0.]
    ui.mod._control_form('USR-1', _orders().iloc[0], _skus(1, 'Kg', 'EMB-1'), _materials(), _products(), True)
    ui.prod.enregistrer_controle_qualite.assert_not_called()
    ui.st.error.assert_called()


def test_no_new_close_with_unconfirmed_of(ui):
    key = ui.mod._closure_key('USR-1')
    ui.st.session_state[key] = {'status': 'uncertain', 'payload': _closure()}
    ui.mod._start_closure('USR-1', _closure(qty=200), True)
    ui.prod.enregistrer_controle_qualite.assert_not_called()


def test_theoretical_consumptions_use_per_unit_rate(ui):
    forecast = ui.mod._theoretical_consumptions(_orders().iloc[0], 100, _materials())
    assert forecast.iloc[0]['besoin_pour_OF'] == 25
    assert forecast.iloc[0]['unite_stock'] == 'Kg'
    ui.prod.get_lignes_recette.assert_called_once_with('REC-0001')


def test_unreadable_recipe_disables_closure(ui):
    ui.prod.get_lignes_recette.return_value = pd.DataFrame()
    ui.st.checkbox.return_value = True
    ui.mod._control_form('USR-1', _orders().iloc[0], _skus(), _materials(), _products(), True)
    assert ui.st.form_submit_button.call_args.kwargs['disabled'] is True
    ui.prod.enregistrer_controle_qualite.assert_not_called()


def test_non_finite_recipe_quantities_fail_closed(ui):
    ui.prod.get_lignes_recette.return_value = pd.DataFrame([{'mp_id': 'MP-1', 'quantite_par_unite': float('nan')}])
    with pytest.raises(ValueError):
        ui.mod._theoretical_consumptions(_orders().iloc[0], 100, _materials())


def test_recipe_preview_is_not_stock_write(ui):
    ui.mod._theoretical_consumptions(_orders().iloc[0], 100, _materials())
    ui.prod.enregistrer_controle_qualite.assert_not_called()
    ui.prod.changer_statut_of.assert_not_called()
