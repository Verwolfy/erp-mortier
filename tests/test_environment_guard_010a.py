"""010-A-01 : tests purs, sans réseau ni connexion aux fournisseurs."""
import pytest

from core.environment_guard import (
    EnvironmentSafetyError, require_supabase_target,
    require_sheet_id, policy_from_environment, policy_from_streamlit,
)

TEST = "https://testxyz98765.supabase.co"
PROD = "https://prodxyz98765.supabase.co"


def cfg(name="TEST", **changes):
    value = {"name": name, "test_supabase_url": TEST,
             "production_supabase_url": PROD,
             "production_enabled": name == "PRODUCTION",
             "test_sheets_ids": {"stocks": "independent-test-stock-id"}}
    value.update(changes)
    return value


def test_test_environment_target():
    assert require_supabase_target(cfg(), TEST) == "TEST"


def test_production_target_requires_explicit_flag():
    assert require_supabase_target(cfg("PRODUCTION"), PROD) == "PRODUCTION"
    with pytest.raises(EnvironmentSafetyError):
        require_supabase_target(cfg("PRODUCTION", production_enabled=False), PROD)
    with pytest.raises(EnvironmentSafetyError):
        require_supabase_target(cfg("PRODUCTION", production_enabled="true"), PROD)


@pytest.mark.parametrize("target", [PROD, "", None, "http://testxyz98765.supabase.co",
                                   "https://testxyz98765.supabase.co/secret",
                                   "https://testxyz98765.supabase.co@evil.example",
                                   "https://testxyz98765.supabase.co?key=x"])
def test_test_blocks_wrong_target(target):
    with pytest.raises(EnvironmentSafetyError):
        require_supabase_target(cfg(), target)


@pytest.mark.parametrize("changes", [
    {"name": "test"}, {"name": None}, {"test_supabase_url": PROD},
    {"production_supabase_url": TEST},
    {"production_supabase_url": None},
])
def test_invalid_configuration_blocks(changes):
    with pytest.raises(EnvironmentSafetyError):
        require_supabase_target(cfg(**changes), TEST)


def test_test_sheets_are_isolated():
    prod_sheets = {"stocks": "production-stock-id", "ventes": "production-sales-id"}
    assert require_sheet_id(cfg(), TEST, "stocks", prod_sheets) == "independent-test-stock-id"
    with pytest.raises(EnvironmentSafetyError):
        require_sheet_id(cfg(test_sheets_ids={"stocks": "production-sales-id"}),
                         TEST, "stocks", prod_sheets)
    with pytest.raises(EnvironmentSafetyError):
        require_sheet_id(cfg(), TEST, "ventes", prod_sheets)
    with pytest.raises(EnvironmentSafetyError):
        require_sheet_id(cfg(), TEST, "unknown", prod_sheets)


def test_prod_sheets_use_only_existing_production_ids():
    ids = {"stocks": "production-stock-id"}
    assert require_sheet_id(cfg("PRODUCTION"), PROD, "stocks", ids) == ids["stocks"]


def test_streamlit_policy_absent_blocks():
    with pytest.raises(EnvironmentSafetyError):
        policy_from_streamlit({})
    assert policy_from_streamlit({"erp_environment": cfg()})["name"] == "TEST"


def test_automated_job_policy():
    variables = {"ERP_ENV": "TEST", "ERP_TEST_SUPABASE_URL": TEST,
                 "ERP_PRODUCTION_SUPABASE_URL": PROD}
    assert require_supabase_target(policy_from_environment(variables), TEST) == "TEST"
    with pytest.raises(EnvironmentSafetyError):
        require_supabase_target(policy_from_environment({}), TEST)


def test_production_unique_sans_ancienne_url_test():
    configuration = cfg("PRODUCTION", test_supabase_url=None)
    assert require_supabase_target(configuration, PROD) == "PRODUCTION"
    assert require_sheet_id(
        configuration, PROD, "stocks",
        {"stocks": "classeur-production"},
    ) == "classeur-production"


@pytest.mark.parametrize("target", [TEST, "", None])
def test_production_sans_test_refuse_une_url_non_autorisee(target):
    with pytest.raises(EnvironmentSafetyError):
        require_supabase_target(
            cfg("PRODUCTION", test_supabase_url=None), target
        )


def test_aucun_test_configure_ne_permet_mode_test():
    with pytest.raises(EnvironmentSafetyError, match="Projet TEST absent"):
        require_supabase_target(cfg(test_supabase_url=None), TEST)
