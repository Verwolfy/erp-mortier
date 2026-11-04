"""Cache de lecture borné au rendu des tableaux de bord."""
from modules.dashboards import service


def test_deux_lectures_une_seule_requete(monkeypatch):
    visits = []
    def read(table):
        visits.append(table)
        return [{"montant": 5}]
    monkeypatch.setattr(service, "fetch_data", read)
    with service.dashboard_read_scope():
        first = service.charger_donnees("factures")
        first.loc[0, "montant"] = 900
        second = service.charger_donnees("factures")
        assert second.loc[0, "montant"] == 5
        assert visits == ["factures"]
    service.charger_donnees("factures")
    assert visits == ["factures", "factures"]


def test_une_erreur_de_lecture_ne_se_met_pas_en_cache(monkeypatch):
    import pytest
    calls = []
    def forbidden(table):
        calls.append(table)
        raise PermissionError("Lecture refusée")
    monkeypatch.setattr(service, "fetch_data", forbidden)
    with service.dashboard_read_scope():
        for _ in range(2):
            with pytest.raises(PermissionError):
                service.charger_donnees("comptes")
    assert calls == ["comptes", "comptes"]


def test_portee_imbriquee_isolee(monkeypatch):
    calls = []
    def read(table):
        calls.append(table)
        return [{"n": len(calls)}]
    monkeypatch.setattr(service, "fetch_data", read)
    with service.dashboard_read_scope():
        assert service.charger_donnees("factures").loc[0, "n"] == 1
        with service.dashboard_read_scope():
            assert service.charger_donnees("factures").loc[0, "n"] == 2
        assert service.charger_donnees("factures").loc[0, "n"] == 1
    assert len(calls) == 2
