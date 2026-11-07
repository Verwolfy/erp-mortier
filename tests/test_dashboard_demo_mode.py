"""Scénarios complets KPI DEMO/SIM, sans réseau et sans écriture Supabase."""
from __future__ import annotations

from datetime import date, datetime
import math

import pandas as pd
import pytest

from core.strict_reads import DataReadError
from modules.dashboards import demo, service, views


TODAY = date(2026, 11, 7)
START = pd.Timestamp("2026-11-01")
END = pd.Timestamp("2026-11-30")


@pytest.fixture
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Accès réel interdit en mode démo")
    monkeypatch.setattr(service, "fetch_data", forbidden)
    monkeypatch.setattr(service, "fetch_data_by_date_range", forbidden)
    monkeypatch.setattr(service, "get_local_now",
                        lambda: datetime(2026, 11, 7, 12, 0))
    return demo.build_demo_dataset(TODAY)


def test_nine_dashboards_render_real_algorithms_on_fictional_rows_offline(offline):
    with service.dashboard_read_scope(demo_rows=offline):
        direction = service.get_kpis_direction()
        pnl = service.get_kpis_pnl(START, END)
        ventes = service.get_kpis_ventes(START, END)
        achats = service.get_kpis_achats(START, END)
        stocks = service.get_kpis_stocks(30)
        prod = service.get_kpis_production(START, END)
        crm = service.get_kpis_crm(START, END)
        rh = service.get_kpis_rh(START, END)
        fin = service.get_kpis_finance(START, END)
        provenance = service.get_dashboard_data_provenance()

    assert direction["ca_mois"] == ventes["ca_ht"] > 0
    assert direction["tresorerie"] > 0 and direction["impayes_30j"] > 0
    assert direction["seuils_stock_absents"] == 1
    assert direction["alertes_stock"] == 2
    assert pnl["ca_ht"] == ventes["ca_ht"]
    assert pnl["cogs"] > 0 and pnl["opex_fournisseurs"] > 0
    assert pnl["ebitda"] == pytest.approx(
        pnl["ca_ht"] - pnl["cogs"] - pnl["opex_fournisseurs"] - pnl["opex_salaires"])
    assert not ventes["evolution_facturation"].empty
    assert ventes["evolution_facturation"]["Facturation HT (DZD)"].sum() == ventas_ca(ventes)
    assert ventes["evolution_facturation"]["Date"].is_monotonic_increasing
    assert achats["montant_total"] > 0 and achats["commandes_retard"] >= 1
    assert not achats["evolution_prix"].empty
    assert (achats["evolution_prix"]["prix_unitaire_dzd"] >= 0).all()
    assert stocks["valeur_totale"] == stocks["valeur_mp"] + stocks["valeur_pf"]
    assert (stocks["lots_perimes"], stocks["lots_a_echeance"],
            stocks["lots_sans_date"]) == (1, 1, 1)
    assert 0 < prod["total_ofs"]
    assert prod["evolution_of"]["OF planifiés"].sum() == prod["total_ofs"]
    assert prod["nb_controles"] > 0
    assert 0 <= prod["taux_rejet"] <= 100
    assert 0 <= prod["taux_cloture"] <= 100
    assert crm["pipeline_pondere"] > 0 and crm["nb_affaires_closes"] == 2
    assert crm["taux_conversion"] == 50
    assert rh["effectif_actif"] == 3 and rh["conges_attente"] == 1
    assert fin["flux_net"] == fin["flux_entrants"] - fin["flux_sortants"]
    assert (fin["evolution_flux"]["Encaissements (DZD)"].sum()
            == fin["flux_entrants"])
    assert (fin["evolution_flux"]["Décaissements (DZD)"].sum()
            == fin["flux_sortants"])
    assert 0 <= fin["taux_lettrage"] <= 100
    assert provenance["marked"] > 0


def ventas_ca(kpis):
    return kpis["ca_ht"]


def test_demo_never_falls_back_to_supabase_on_missing_source(offline):
    missing = {k: v for k, v in offline.items() if k != "factures"}
    with service.dashboard_read_scope(demo_rows=missing):
        with pytest.raises(DataReadError, match="démo absente|démonstration absente"):
            service.charger_donnees("factures")
        with pytest.raises(DataReadError, match="Source de démonstration absente"):
            service._lire_periode("factures", "date", "2026-11-01", "2026-11-30")


def test_data_is_copied_and_not_shared_across_screens(offline):
    with service.dashboard_read_scope(demo_rows=offline):
        original = service.charger_donnees("factures")
        original.loc[0, "montant_ht"] = 999999999
        second = service.charger_donnees("factures")
        assert second.loc[0, "montant_ht"] != 999999999
        assert not service._lire_periode("factures", "date", "2026-11-01", "2026-11-30").empty
    assert offline["factures"][0]["montant_ht"] != 999999999


def test_real_mode_uses_original_reads_after_demo_scope_exits(monkeypatch, offline):
    calls = []
    monkeypatch.setattr(service, "fetch_data",
                        lambda table: calls.append(table) or [{"facture_id": "FAC-REEL"}])
    with service.dashboard_read_scope(demo_rows=offline):
        assert service.charger_donnees("factures")["facture_id"].str.startswith("DEMO").all()
    with service.dashboard_read_scope():
        assert service.charger_donnees("factures")["facture_id"].tolist() == ["FAC-REEL"]
    assert calls == ["factures"]


def test_date_range_never_uses_out_of_period_rows(offline):
    with service.dashboard_read_scope(demo_rows=offline):
        history = service._lire_periode(
            "factures", "date", "2026-11-01", "2026-11-30")
        assert "DEMO-KPI-ANCIEN" not in history["facture_id"].tolist()
        assert "DEMO-KPI-BROUILLON" in history["facture_id"].tolist()
        # Le filtre de date ne doit pas réécrire silencieusement les statuts.
        ventes = service.get_kpis_ventes(START, END)
        assert ventes["nb_factures"] < len(history)


def test_scenario_has_no_raw_keys_or_unprefixed_identifiers():
    rows = demo.build_demo_dataset(TODAY)
    assert len(rows) >= 15
    for name, table in rows.items():
        assert isinstance(table, list), name
        for row in table:
            for key, value in row.items():
                if key.endswith("_id") and value is not None:
                    assert str(value).startswith(("DEMO-KPI-", "SIM-KPI-")), (name, key, value)
            assert "service_role" not in str(row).lower()


@pytest.mark.parametrize("bad_input", [None, [], {"factures": [1]}])
def test_invalid_demo_payload_rejected(bad_input):
    if bad_input is None:
        # None is the intentionally supported real-mode sentinel.
        with service.dashboard_read_scope(demo_rows=None):
            pass
    else:
        with pytest.raises(ValueError):
            with service.dashboard_read_scope(demo_rows=bad_input):
                pass


def test_demo_in_january_has_at_least_one_daily_point():
    dataset = demo.build_demo_dataset(date(2027, 1, 1))
    invoices = [x for x in dataset["factures"] if x["statut"] == "VALIDE"]
    assert any(x["date"] == "2027-01-01" for x in invoices)


def test_wrapper_routes_demo_without_ever_changing_real_schemas(monkeypatch):
    seen = []
    old_state = {"user": {"role": "ADMIN"}, "_erp_dashboard_demo_mode": True}
    monkeypatch.setattr(views.st, "session_state", old_state)
    monkeypatch.setattr(views, "get_local_now",
                        lambda: datetime(2026, 11, 7, 12, 0))

    def render():
        seen.append(service.get_kpis_ventes(START, END)["nb_factures"])

    def forbidden(*args, **kwargs):
        raise AssertionError("Source Supabase consultée")
    monkeypatch.setattr(service, "fetch_data", forbidden)
    monkeypatch.setattr(service, "fetch_data_by_date_range", forbidden)
    monkeypatch.setattr(views, "_show_dashboards_page_impl", render)
    views.show_dashboards_page()
    assert seen == [4]
