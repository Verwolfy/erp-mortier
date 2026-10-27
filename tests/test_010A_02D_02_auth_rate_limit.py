import pytest
from unittest.mock import Mock

from core import auth_rate_limit as rate


@pytest.fixture
def client(monkeypatch):
    fake = Mock()
    monkeypatch.setattr(rate, "get_supabase_client", lambda: fake)
    return fake


TOKEN = "123e4567-e89b-42d3-a456-426614174000"


def test_begin_success(client):
    client.rpc.return_value.execute.return_value.data = TOKEN
    assert rate.begin_login_attempt("admin") == TOKEN


def test_begin_blocked(client):
    client.rpc.return_value.execute.return_value.data = None
    assert rate.begin_login_attempt("admin") is None


def test_invalid_login_denied(client):
    assert rate.begin_login_attempt("") is None
    client.rpc.assert_not_called()


def test_begin_unavailable_fails_closed(client):
    client.rpc.side_effect = RuntimeError("backend down")
    with pytest.raises(rate.AuthRateLimitUnavailable):
        rate.begin_login_attempt("admin")


def test_finish_success(client):
    client.rpc.return_value.execute.return_value.data = True
    rate.finish_login_attempt(TOKEN, "SUCCESS")
    client.rpc.assert_called_with(
        "erp_auth_finish",
        {"p_token": TOKEN, "p_outcome": "SUCCESS"},
    )


def test_finish_not_confirmed_fails_closed(client):
    client.rpc.return_value.execute.return_value.data = False
    with pytest.raises(rate.AuthRateLimitUnavailable):
        rate.finish_login_attempt(TOKEN, "SUCCESS")


def test_invalid_outcome_denied(client):
    with pytest.raises(ValueError):
        rate.finish_login_attempt(TOKEN, "UNKNOWN")
    client.rpc.assert_not_called()
