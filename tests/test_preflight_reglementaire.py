"""Tests isolés de préflight, aucun SQL ni réseau."""
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from core.preflight_reglementaire import examiner_referentiels, lire_preflight, PreflightIndisponible

def snapshots():
    return {
        "parametres_reglementaires": [
            {"code":"TVA_TAUX_NORMAL","valeur":"0.190000000000","unite":"fraction","statut_juridique":"en_vigueur","niveau_confiance":"CONFIRMEE"},
            {"code":"TVA_TAUX_REDUIT","valeur":"0.09","unite":"fraction","statut_juridique":"en_vigueur","niveau_confiance":"CONFIRMEE"}],
        "regles_reglementaires":[{"code":"TVA_G50_MENSUEL_REGIME_REEL","donnees":{"application_entreprise":"NON_CLASSEE"},"statut_juridique":"en_vigueur","niveau_confiance":"CONFIRMEE"}],
        "scf_plan_comptes":[{"numero_compte":"411","actif":False,"mouvementable":False},{"numero_compte":"512","actif":False,"mouvementable":False}],
        "scf_exercices":[], "scf_journaux":[]
    }

def test_preflight_ne_confond_pas_references_et_activation():
    r=examiner_referentiels(snapshots())
    assert r["reference_tva_officielle"] is True
    assert r["classification_tva_produits"]=="NON_VERIFIEE"
    assert r["g50_conditionnelle"] is True
    assert r["facturation_reglementaire_prete"] is False
    assert r["comptabilisation_scf_prete"] is False
    assert r["comptes_scf_mouvementables"]==0

@pytest.mark.parametrize("mutation",[
    lambda d:d.pop("scf_journaux"),
    lambda d:d["parametres_reglementaires"].append(d["parametres_reglementaires"][0]),
    lambda d:d["parametres_reglementaires"][0].update(valeur="0.20"),
    lambda d:d["parametres_reglementaires"][0].update(valeur="NaN"),
    lambda d:d["scf_plan_comptes"].append(d["scf_plan_comptes"][0]),
    lambda d:d["scf_plan_comptes"][0].update(actif="NON"),
    lambda d:d["regles_reglementaires"][0].update(donnees="invalide"),
])
def test_reference_incoherente_refusee(mutation):
    d=snapshots()
    mutation(d)
    with pytest.raises(PreflightIndisponible):
        examiner_referentiels(d)

def test_lecture_compteurs_exacts():
    data=snapshots()
    db=Mock()
    def table(name):
        q=Mock()
        q.select.return_value=q
        q.range.return_value=q
        q.execute.return_value=SimpleNamespace(data=data[name],count=len(data[name]))
        return q
    db.table.side_effect=table
    result=lire_preflight(db_client=db)
    assert result["statut"]=="CONFIGURATION_METIER_A_COMPLETER"
    assert db.table.call_count==5

def test_refus_lecture_tronquee():
    db=Mock()
    q=db.table.return_value.select.return_value.range.return_value
    q.execute.return_value=SimpleNamespace(data=[],count=1)
    with pytest.raises(PreflightIndisponible):
        lire_preflight(db_client=db)

def test_refus_sans_client():
    with pytest.raises(PreflightIndisponible):
        lire_preflight(db_client=None)
