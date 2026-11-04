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


def test_scope_failures_not_cached(monkeypatch):
    import pytest
    calls = []
    def deny(table):
        calls.append(table)
        raise PermissionError("Refus RBAC")
    monkeypatch.setattr(service, "fetch_data", deny)
    with service.dashboard_read_scope():
        for _ in range(2):
            with pytest.raises(PermissionError):
                service.charger_donnees("comptes")
    assert calls == ["comptes", "comptes"]


def test_nested_scope_restores_previous_read(monkeypatch):
    calls = []
    def read(table):
        calls.append(table)
        return [{"montant": len(calls)}]
    monkeypatch.setattr(service, "fetch_data", read)
    with service.dashboard_read_scope():
        assert service.charger_donnees("factures").loc[0, "montant"] == 1
        with service.dashboard_read_scope():
            assert service.charger_donnees("factures").loc[0, "montant"] == 2
        assert service.charger_donnees("factures").loc[0, "montant"] == 1
    assert calls == ["factures", "factures"]


def test_achats_aucune_ligne_chargee_quand_periode_vide(monkeypatch):
    import pandas as pd
    queried = []
    def read(table):
        queried.append(table)
        return []
    monkeypatch.setattr(service, "fetch_data", read)
    monkeypatch.setattr(service, "fetch_data_by_date_range", lambda *args: [])
    monkeypatch.setattr(service, "get_local_now", lambda: pd.Timestamp("2026-11-01"))
    result = service.get_kpis_achats(
        pd.Timestamp("2026-11-01"), pd.Timestamp("2026-11-30"))
    assert result["montant_total"] == 0
    assert "lignes_achats" not in queried


def test_pnl_aucune_ligne_facture_ni_cout_si_aucune_facture(monkeypatch):
    import pandas as pd
    queried = []
    def read(table):
        queried.append(table)
        return []
    monkeypatch.setattr(service, "fetch_data", read)
    monkeypatch.setattr(service, "fetch_data_by_date_range", lambda *args: [])
    monkeypatch.setattr(service, "validated_documents", lambda frame: pd.DataFrame(
        {"montant_ht": [], "type_facture": []}))
    monkeypatch.setattr(service, "client_invoices", lambda frame: frame)
    monkeypatch.setattr(service, "supplier_operating_payments", lambda *args: 0.0)
    monkeypatch.setattr(service, "payroll_net_for_period", lambda *args: 0.0)
    result = service.get_kpis_pnl(
        pd.Timestamp("2026-11-01"), pd.Timestamp("2026-11-30"))
    assert result["cogs"] == 0
    assert "lignes_facture" not in queried
    assert "stock_actuel_pf" not in queried
