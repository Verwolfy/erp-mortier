"""ENV-01 : refuser une cible de production AVANT tout appel réseau."""
from __future__ import annotations

from unittest.mock import Mock

import pytest

from core.environment_guard import EnvironmentSafetyError
from core.integration_test_guard import require_integration_test_target

PROD = "https://prod98765.supabase.co"
TEST = "https://isolated98765.supabase.co"


def config(**updates):
    data = {
        "ERP_ENV": "TEST",
        "ERP_PRODUCTION_SUPABASE_URL": PROD,
        "ERP_TEST_SUPABASE_URL": TEST,
        "ERP_INTEGRATION_SUPABASE_URL": TEST,
        "ERP_INTEGRATION_CONFIRM": "I_CONFIRM_SEPARATE_TEST_DATABASE",
        "ERP_TEST_SUPABASE_KEY": "fake-test-key-not-real",
        "ERP_PRODUCTION_SUPABASE_KEY": "fake-prod-key-not-real",
    }
    data.update(updates)
    return data


def test_independent_test_environment_passes_without_network():
    assert require_integration_test_target(config()) == "TEST"


@pytest.mark.parametrize("updates", [
    {"ERP_ENV": "PRODUCTION"},
    {"ERP_ENV": ""},
    {"ERP_ENV": None},
    {"ERP_INTEGRATION_CONFIRM": None},
    {"ERP_INTEGRATION_CONFIRM": "yes"},
    {"ERP_INTEGRATION_SUPABASE_URL": PROD},
    {"ERP_INTEGRATION_SUPABASE_URL": ""},
    {"ERP_INTEGRATION_SUPABASE_URL": "https://isolated98765.supabase.co/hidden"},
    {"ERP_TEST_SUPABASE_URL": PROD},
    {"ERP_TEST_SUPABASE_URL": None},
    {"ERP_PRODUCTION_SUPABASE_URL": None},
    {"ERP_TEST_SUPABASE_KEY": None},
    {"ERP_TEST_SUPABASE_KEY": ""},
    {"ERP_TEST_SUPABASE_KEY": "same", "ERP_PRODUCTION_SUPABASE_KEY": "same"},
    {"SUPABASE_URL": PROD},
    {"ERP_RUNTIME_SUPABASE_URL": PROD},
    {"SUPABASE_URL": "http://isolated98765.supabase.co"},
])
def test_invalid_targets_always_refuse_before_network(updates):
    with pytest.raises(EnvironmentSafetyError):
        require_integration_test_target(config(**updates))


def test_prod_secrets_not_exposed_in_error():
    data = config(ERP_TEST_SUPABASE_KEY="secret_should_not_leak",
                  ERP_PRODUCTION_SUPABASE_KEY="secret_should_not_leak")
    with pytest.raises(EnvironmentSafetyError) as exc:
        require_integration_test_target(data)
    assert "secret_should_not_leak" not in str(exc.value)
    assert PROD not in str(exc.value)
    assert TEST not in str(exc.value)


def test_generic_alias_may_only_point_to_independent_test():
    assert require_integration_test_target(config(SUPABASE_URL=TEST)) == "TEST"


def test_cli_denies_unconfigured_runner_without_any_network(monkeypatch, capsys):
    import scripts.preflight_integration_test as cli
    monkeypatch.setattr(cli.os, "environ", {})
    assert cli.main() == 2
    output = capsys.readouterr().out
    assert "REFUS" in output
    assert PROD not in output and TEST not in output


def test_cli_only_certifies_preflight_not_database_availability(monkeypatch, capsys):
    import scripts.preflight_integration_test as cli
    monkeypatch.setattr(cli.os, "environ", config())
    assert cli.main() == 0
    assert "aucune connexion effectuée" in capsys.readouterr().out
