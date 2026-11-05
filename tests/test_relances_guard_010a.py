"""Tests de l'absence d'envoi en TEST ; aucune connexion SMTP ou Supabase."""
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import Mock

import pandas as pd

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "envoyer_relances.py"
TEST_URL = "https://testxyz98765.supabase.co"
PROD_URL = "https://prodxyz98765.supabase.co"


def _loaded(monkeypatch):
    supa = types.ModuleType("supabase")
    supa.create_client = Mock(return_value=object())
    monkeypatch.setitem(sys.modules, "supabase", supa)
    spec = importlib.util.spec_from_file_location("relances_010_a", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.SUPABASE_URL = TEST_URL
    module.SUPABASE_KEY = "dummy-test-key"
    module.get_factures_echues = Mock(return_value=pd.DataFrame([{
        "facture_id": "F-TEST", "client_id": "C-TEST", "montant_ttc": "100",
        "montant_paye": "0", "date_echeance": "2026-01-01",
    }]))
    module.get_clients = Mock(return_value=pd.DataFrame([{
        "client_id": "C-TEST", "nom": "Client fictif", "email_contact": "fake@example.test",
    }]))
    module.envoyer_email_relance = Mock()
    return module, supa


def _set_env(monkeypatch, mode="TEST", enabled="false", email="true"):
    data = {"ERP_ENV": mode, "ERP_TEST_SUPABASE_URL": TEST_URL,
            "ERP_PRODUCTION_SUPABASE_URL": PROD_URL,
            "ERP_PRODUCTION_ENABLED": enabled,
            "ERP_REMINDER_MINIMUM_DZD": "10",
            "ERP_ENABLE_EMAIL_SEND": email}
    for name, value in data.items():
        monkeypatch.setenv(name, value)


def test_test_mode_never_sends_even_with_email_flag(monkeypatch):
    module, supa = _loaded(monkeypatch)
    _set_env(monkeypatch)
    assert module.main() == 0
    supa.create_client.assert_called_once()
    module.envoyer_email_relance.assert_not_called()


def test_wrong_project_stops_before_network(monkeypatch):
    module, supa = _loaded(monkeypatch)
    _set_env(monkeypatch)
    module.SUPABASE_URL = PROD_URL
    assert module.main() == 2
    supa.create_client.assert_not_called()


def test_production_disabled_stops_before_network(monkeypatch):
    module, supa = _loaded(monkeypatch)
    _set_env(monkeypatch, mode="PRODUCTION", enabled="false")
    module.SUPABASE_URL = PROD_URL
    assert module.main() == 2
    supa.create_client.assert_not_called()


def test_missing_reminder_threshold_stops_before_network(monkeypatch):
    module, supa = _loaded(monkeypatch)
    _set_env(monkeypatch)
    monkeypatch.delenv("ERP_REMINDER_MINIMUM_DZD")
    assert module.main() == 2
    supa.create_client.assert_not_called()


def test_demo_invoice_and_demo_client_excluded_in_production(monkeypatch):
    module, _ = _loaded(monkeypatch)
    _set_env(monkeypatch, mode="PRODUCTION", enabled="true", email="true")
    monkeypatch.setenv("SMTP_USER", "smtp-simule@example.test")
    monkeypatch.setenv("SMTP_PASSWORD", "faux-secret-de-test")
    module.SMTP_USER = "smtp-simule@example.test"
    module.SMTP_PASSWORD = "faux-secret-de-test"
    module.SUPABASE_URL = PROD_URL
    module.get_factures_echues = Mock(return_value=pd.DataFrame([
        {"facture_id": "DEMO26_FAC2", "client_id": "DEMO26_CLI2",
         "montant_ttc": "11900", "montant_paye": "0", "date_echeance": "2026-09-30"},
        {"facture_id": "FACTURE-REELLE", "client_id": "DEMO26_CLI1",
         "montant_ttc": "500", "montant_paye": "0", "date_echeance": "2026-09-30"},
        {"facture_id": "FAC-PROD-TEST", "client_id": "CLIENT-TEST",
         "montant_ttc": "300", "montant_paye": "100", "date_echeance": "2026-09-30"},
    ]))
    module.get_clients = Mock(return_value=pd.DataFrame([
        {"client_id": "DEMO26_CLI1", "nom": "[FICTIF] Test",
         "email_contact": "fiction@example.test"},
        {"client_id": "DEMO26_CLI2", "nom": "[FICTIF] Test",
         "email_contact": "fiction@example.test"},
        {"client_id": "CLIENT-TEST", "nom": "Client test non DEMO26",
         "email_contact": "valid@example.test"},
    ]))
    assert module.main() == 0
    module.envoyer_email_relance.assert_called_once()
    assert module.envoyer_email_relance.call_args.kwargs["facture_id"] == "FAC-PROD-TEST"


def test_only_demo_invoices_produce_no_emails_or_eligible_count(monkeypatch, capsys):
    module, _ = _loaded(monkeypatch)
    _set_env(monkeypatch, mode="PRODUCTION", enabled="true", email="true")
    monkeypatch.setenv("SMTP_USER", "smtp-simule@example.test")
    monkeypatch.setenv("SMTP_PASSWORD", "faux-secret-de-test")
    module.SMTP_USER = "smtp-simule@example.test"
    module.SMTP_PASSWORD = "faux-secret-de-test"
    module.SUPABASE_URL = PROD_URL
    module.get_factures_echues = Mock(return_value=pd.DataFrame([
        {"facture_id": "DEMO26_FAC2", "client_id": "DEMO26_CLI2",
         "montant_ttc": "11900", "montant_paye": "0",
         "date_echeance": "2026-09-30"},
    ]))
    assert module.main() == 0
    module.envoyer_email_relance.assert_not_called()
    assert "Relances eligibles : 0" in capsys.readouterr().out


def test_integrated_sim26_scenario_never_generates_reminder(monkeypatch, capsys):
    module, _ = _loaded(monkeypatch)
    _set_env(monkeypatch, mode="PRODUCTION", enabled="true", email="true")
    module.SUPABASE_URL = PROD_URL
    module.SMTP_USER = "simulation@example.test"
    module.SMTP_PASSWORD = "test-only"
    module.get_factures_echues = Mock(return_value=pd.DataFrame([
        {"facture_id": "SIM26_INV", "client_id": "SIM26_CLI",
         "montant_ttc": "2380", "montant_paye": "0",
         "date_echeance": "2026-10-23"},
    ]))
    module.get_clients = Mock(return_value=pd.DataFrame([
        {"client_id": "SIM26_CLI", "nom": "[FICTIF] Client SIM26",
         "email_contact": "fiction@example.test"},
    ]))
    assert module.main() == 0
    module.envoyer_email_relance.assert_not_called()
    assert "Relances eligibles : 0" in capsys.readouterr().out
