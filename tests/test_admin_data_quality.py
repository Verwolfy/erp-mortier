"""Audit transversal : aucune écriture, anonymisation des résultats."""
import pytest

from modules.admin.data_quality import audit_autorise, audit_referentiels


def _fixtures():
    return {
        "clients": [
            {"client_id": "C1", "nom": "Client actif", "actif": "OUI"},
            {"client_id": "C1", "nom": "", "actif": "NON"},
            {"client_id": "", "nom": "Sans identifiant", "actif": "OUI"},
        ],
        "fournisseurs": [{"fournisseur_id": "F1", "nom": "Fournisseur", "actif": "OUI"}],
        "produits": [{"pf_id": "P1", "nom": "Produit A", "actif": "OUI"}],
        "sku_conditionnement": [
            {"sku_id": "S1", "pf_id": "P1", "actif": "OUI"},
            {"sku_id": "S2", "pf_id": "P2", "actif": "OUI"},
            {"sku_id": "S3", "pf_id": "", "actif": "NON"},
        ],
        "matieres_premieres": [{"mp_id": "M1", "nom": "Matière", "actif": "OUI"}],
    }


def test_audit_signale_duplicats_manquants_et_liens_non_valides():
    dataset = _fixtures()
    result = audit_referentiels(dataset)
    clients = result[0]
    assert clients["Enregistrements"] == 3
    assert clients["ID en doublon"] == 1
    assert clients["ID manquants"] == 1
    assert clients["Désignations manquantes"] == 1
    assert clients["Inactifs / à vérifier"] == 1
    assert result[3]["Liens invalides"] == 2
    assert all("nom" not in row and "client_id" not in row for row in result)


def test_audit_refuse_partiel_et_ne_masque_pas_refus_acces():
    dataset = _fixtures()
    def denied(name):
        if name == "produits":
            raise PermissionError("Refus RBAC")
        return dataset[name]
    with pytest.raises(PermissionError):
        audit_autorise(reader=denied)
    assert audit_autorise(reader=lambda table: dataset[table]) == audit_referentiels(dataset)
    with pytest.raises(ValueError):
        audit_referentiels({**dataset, "clients": ["pas un dictionnaire"]})


def test_interface_qualite_ne_fait_pas_decriture():
    from pathlib import Path
    view = Path("modules/admin/views.py").read_text(encoding="utf-8")
    code = Path("modules/admin/data_quality.py").read_text(encoding="utf-8")
    assert "Analyser les référentiels autorisés" in view
    assert "audit_autorise()" in view
    assert "fetch_data_paginated" in code
    assert "insert_hybrid" not in code and "update_hybrid" not in code


def test_liens_ventes_achats_production_sans_donnees_personnelles():
    from modules.admin.data_quality import audit_operations, audit_operations_autorise
    data = {
        "clients": [{"client_id": "C1"}],
        "fournisseurs": [{"fournisseur_id": "F1"}],
        "produits": [{"pf_id": "P1"}],
        "commandes_ventes": [
            {"commande_vente_id": "V1", "client_id": "C1"},
            {"commande_vente_id": "V2", "client_id": "CX"},
        ],
        "commandes_achats": [{"commande_achat_id": "A1", "fournisseur_id": ""}],
        "ordres_fabrication": [{"of_id": "OF1", "pf_id": "P1"}],
    }
    rows = audit_operations(data)
    assert rows[0]["Liens introuvables"] == 1
    assert rows[1]["Liens manquants"] == 1
    assert rows[2]["Liens introuvables"] == 0
    assert all("client_id" not in row and "fournisseur_id" not in row
               for row in rows)
    assert audit_operations_autorise(reader=lambda table: data[table]) == rows


def test_liens_metier_refusent_une_lecture_partielle():
    from modules.admin.data_quality import audit_operations_autorise
    def denied(table):
        if table == "ordres_fabrication":
            raise PermissionError("Accès interdit")
        return []
    with pytest.raises(PermissionError):
        audit_operations_autorise(reader=denied)
