"""Tests des audits Finance/RH à partir d'échantillons fictifs."""
from modules.admin.finance_quality import audit_finance
from modules.admin.rh_quality import audit_rh


def test_finance_references_et_allocations():
    data = {
        "comptes": [{"compte_id": "B1"}],
        "reglements": [
            {"reglement_id": "R1", "compte_id": "B1",
             "montant_total": "100", "montant_alloue": "150"},
        ],
        "lettrage": [{"reglement_id": "R1", "montant_applique": "10"}],
        "ecritures_comptables": [{"compte_id": "B1", "debit": "5", "credit": "0"}],
    }
    result = audit_finance(data)
    assert result[0]["Allocations supérieures au règlement"] == 1
    assert result[0]["Liens introuvables"] == 0


def test_rh_periodes_et_taches():
    data = {
        "employes": [{"employe_id": "E1"}],
        "demandes_conges": [
            {"employe_id": "E1", "date_debut": "2026-11-08",
             "date_fin": "2026-11-05"},
        ],
        "projets": [{"projet_id": "P1"}],
        "taches": [{"tache_id": "T1", "projet_id": "P404", "assigne_a": "E1"}],
        "feuilles_de_temps": [
            {"employe_id": "E1", "tache_id": "T1",
             "date": "invalide", "heures": "25"},
        ],
    }
    result = audit_rh(data)
    assert result[0]["Périodes inversées"] == 1
    assert result[1]["Liens introuvables"] == 1
    assert result[3]["Durées invalides"] == 1
    assert result[3]["Dates invalides"] == 1
