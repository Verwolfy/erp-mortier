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


def test_lecture_refusee_et_panneau_raccorde():
    from pathlib import Path
    import pytest
    from modules.admin.finance_quality import audit_finance_autorise
    from modules.admin.rh_quality import audit_rh_autorise

    def refused(table):
        raise PermissionError("Droits insuffisants")

    with pytest.raises(PermissionError):
        audit_finance_autorise(reader=refused)
    with pytest.raises(PermissionError):
        audit_rh_autorise(reader=refused)
    view = Path("modules/admin/views.py").read_text(encoding="utf-8")
    assert "render_finance_rh_quality()" in view
    content = Path("modules/admin/finance_rh_quality_view.py").read_text(encoding="utf-8")
    assert "Analyser la cohérence Finance" in content
    assert "Analyser la cohérence RH" in content
    for file in ("modules/admin/finance_quality.py", "modules/admin/rh_quality.py"):
        code = Path(file).read_text(encoding="utf-8")
        assert "fetch_data_paginated" in code
        assert "insert_hybrid" not in code
        assert "update_hybrid" not in code
