"""Empreintes documentaires reproductibles, sans base de données."""
from copy import deepcopy

import pytest

from modules.documents.trace_integrity import canonical_draft, draft_sha256
from modules.documents.views import new_draft


def test_empreinte_stable_quelque_soit_ordre_des_cles():
    doc = new_draft("Devis")
    doc["items"] = [{"reference": "SKU-A", "designation": "Produit A",
                     "quantite": "2", "prix_unitaire": "100"}]
    copy = deepcopy(doc)
    reordered = {key: copy[key] for key in reversed(tuple(copy.keys()))}
    before = deepcopy(doc)
    assert draft_sha256(doc) == draft_sha256(reordered)
    assert len(draft_sha256(doc)) == 64
    assert doc == before


def test_empreinte_change_avec_prix_tiers_et_ordre_des_lignes():
    doc = new_draft("Devis")
    doc["tiers_nom"] = "Client A"
    doc["items"] = [
        {"reference": "A", "designation": "A", "quantite": "2", "prix_unitaire": "100"},
        {"reference": "B", "designation": "B", "quantite": "3", "prix_unitaire": "20"},
    ]
    digest = draft_sha256(doc)
    another = deepcopy(doc)
    another["tiers_nom"] = "Client B"
    assert draft_sha256(another) != digest
    another = deepcopy(doc)
    another["items"][0]["prix_unitaire"] = "110"
    assert draft_sha256(another) != digest
    another = deepcopy(doc)
    another["items"].reverse()
    assert draft_sha256(another) != digest


def test_empreinte_refuse_identifiant_ou_statut_falsifie():
    doc = new_draft("Bon de livraison")
    doc["trace_id"] = "NG-FAUX"
    with pytest.raises(ValueError):
        draft_sha256(doc)
    doc = new_draft("Bon de livraison")
    doc["statut"] = "VALIDE"
    with pytest.raises(ValueError):
        draft_sha256(doc)
    doc = new_draft("Devis")
    doc["items"] = [{"reference": "A", "quantite": "5"}]
    with pytest.raises(ValueError, match="Montants incomplets"):
        draft_sha256(doc)


def test_canonical_ne_contient_pas_de_champs_non_contractuels():
    doc = new_draft("Bon de livraison")
    doc["token_secret"] = "ne-doit-pas-apparaitre"
    payload = canonical_draft(doc)
    assert b"token_secret" not in payload
    assert b"ne-doit-pas-apparaitre" not in payload
