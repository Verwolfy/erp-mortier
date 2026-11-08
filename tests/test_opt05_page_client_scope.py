"""OPT-05 : un seul client par page stricte, sans cache entre utilisateurs.

Tout le backend est simulé : aucun secret réel, réseau ni écriture SQL.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from core import db_service as db, strict_reads as reads
from core.query_diagnostics import query_metrics_scope, query_metrics_snapshot


class LocalQuery:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.bounds = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def range(self, first, last):
        self.bounds = (first, last)
        return self

    def execute(self):
        self.client.events.append((self.client.serial, self.table))
        if self.table == "users":
            rows = []
            if self.client.active["value"]:
                rows = [{"user_id": self.client.user_id, "role": "ADMIN", "actif": "OUI"}]
            return SimpleNamespace(data=rows)
        assert self.table == "factures"
        source = self.client.rows
        if self.bounds:
            start, end = self.bounds
            source = source[start:min(end + 1, start + self.client.api_cap)]
        if self.client.revoke_after_first_select and not self.client.revoke_seen["value"]:
            self.client.revoke_seen["value"] = True
            self.client.active["value"] = False
        return SimpleNamespace(data=list(source), count=len(self.client.rows))


class LocalClient:
    def __init__(self, serial, events, rows, api_cap, active, revoke_seen,
                 revoke_after_first_select, user_id):
        self.serial = serial
        self.events = events
        self.rows = rows
        self.api_cap = api_cap
        self.active = active
        self.revoke_seen = revoke_seen
        self.revoke_after_first_select = revoke_after_first_select
        self.user_id = user_id

    def table(self, name):
        return LocalQuery(self, name)


@pytest.fixture
def fake_env(monkeypatch):
    state = {"authenticated": True, "user": {"user_id": "USER-TEST-1", "role": "ADMIN"}}
    secrets = {"supabase": {"url": "https://fake-project.invalid", "key": "placeholder-key"}}
    monkeypatch.setattr(db.st, "session_state", state)
    monkeypatch.setattr(db.st, "secrets", secrets)
    monkeypatch.setattr(db, "policy_from_streamlit", lambda _: object())
    monkeypatch.setattr(db, "require_supabase_target", lambda *_: None)
    events, clients = [], []
    active, revoked = {"value": True}, {"value": False}
    settings = {"rows": [{"facture_id": "FAC-A"}, {"facture_id": "FAC-B"}],
                "api_cap": 500, "revoke_after_first_select": False}

    def factory(_url, _key):
        client = LocalClient(len(clients) + 1, events, settings["rows"],
                             settings["api_cap"], active, revoked,
                             settings["revoke_after_first_select"],
                             state["user"]["user_id"])
        clients.append(client)
        return client

    monkeypatch.setattr(db, "create_client", factory)
    return SimpleNamespace(state=state, secrets=secrets, clients=clients,
                           events=events, active=active, revoked=revoked,
                           settings=settings)


def test_one_client_for_authorization_and_select_per_page(fake_env):
    env = fake_env
    with query_metrics_scope():
        rows = reads.fetch_data_strict("factures", only_primary_key=True)
        metrics = query_metrics_snapshot()
    assert [row["facture_id"] for row in rows] == ["FAC-A", "FAC-B"]
    assert len(env.clients) == 1
    assert env.events == [(1, "users"), (1, "factures")]
    assert metrics["checks"] == 1
    assert metrics["selects"] == 1
    assert metrics["clients"] == 1


def test_new_client_for_every_next_page_and_fresh_server_auth(fake_env):
    env = fake_env
    env.settings["api_cap"] = 1
    with query_metrics_scope():
        rows = reads.fetch_data_strict("factures", only_primary_key=True)
        metrics = query_metrics_snapshot()
    assert len(rows) == 2
    assert len(env.clients) == 2
    assert env.events == [
        (1, "users"), (1, "factures"),
        (2, "users"), (2, "factures"),
    ]
    assert (metrics["checks"], metrics["selects"], metrics["clients"]) == (2, 2, 2)


def test_revocation_between_pages_blocks_second_data_select(fake_env):
    env = fake_env
    env.settings["api_cap"] = 1
    env.settings["revoke_after_first_select"] = True
    with pytest.raises(PermissionError):
        reads.fetch_data_strict("factures", only_primary_key=True)
    assert env.events == [
        (1, "users"), (1, "factures"), (2, "users"),
    ]
    assert len(env.clients) == 2


def test_history_page_uses_one_client_with_fresh_permission(fake_env):
    env = fake_env
    rows, count = reads.fetch_history_page_strict("factures")
    assert len(rows) == count == 2
    assert len(env.clients) == 1
    assert env.events == [(1, "users"), (1, "factures")]


def test_without_strict_page_scope_no_client_is_shared(fake_env):
    env = fake_env
    assert db.get_supabase_client() is not db.get_supabase_client()
    assert len(env.clients) == 2


def test_nested_page_scopes_restore_previous_client(fake_env):
    env = fake_env
    with db.strict_read_page_client_scope():
        parent = db.get_supabase_client()
        with db.strict_read_page_client_scope():
            child = db.get_supabase_client()
            assert child is db.get_supabase_client()
        assert parent is db.get_supabase_client()
    assert parent is not child
    assert db.get_supabase_client() not in (parent, child)
    assert len(env.clients) == 3


def test_changing_user_during_a_page_fails_closed(fake_env):
    env = fake_env
    with db.strict_read_page_client_scope():
        old = db.get_supabase_client()
        env.state["user"] = {"user_id": "USER-TEST-2", "role": "ADMIN"}
        with pytest.raises(PermissionError, match="Contexte de lecture"):
            db.get_supabase_client()
    assert len(env.clients) == 1
    assert old is not db.get_supabase_client()


def test_changing_target_key_during_a_page_fails_closed(fake_env):
    env = fake_env
    with db.strict_read_page_client_scope():
        db.get_supabase_client()
        env.secrets["supabase"]["key"] = "rotated-placeholder"
        with pytest.raises(PermissionError, match="Contexte de lecture"):
            db.get_supabase_client()
    assert len(env.clients) == 1


def test_denied_first_page_never_queries_business_data(fake_env):
    env = fake_env
    env.active["value"] = False
    with pytest.raises(PermissionError):
        reads.fetch_data_strict("factures")
    assert env.events == [(1, "users")]
    assert len(env.clients) == 1


def test_exception_releases_page_scoped_client(fake_env, monkeypatch):
    env = fake_env
    def fail_permission(_table):
        db.get_supabase_client()
        raise PermissionError("Refus de test")

    monkeypatch.setattr(db, "_require_read_permission", fail_permission)
    with pytest.raises(PermissionError):
        reads.fetch_data_strict("factures")
    assert len(env.clients) == 1
    assert db.get_supabase_client() is not env.clients[0]
    assert len(env.clients) == 2
