"""Tests isoles : aucune connexion a Supabase, Sheets ou Streamlit Cloud."""
import importlib.util
import sys
import types
from datetime import datetime
from pathlib import Path

import pytest

FILE = Path(__file__).parents[1] / "core" / "db_service.py"


class Reply:
    def __init__(self, data):
        self.data = data


class Query:
    def __init__(self, db, table):
        self.db, self.table = db, table
        self.action = None
        self.payload = None
        self.predicates = []
        self.page = None
        self.limit_n = None
        self.sort = None
        self.cols = "*"

    def select(self, cols):
        self.action, self.cols = "select", cols
        return self

    def insert(self, data):
        self.action, self.payload = "insert", data
        return self

    def update(self, data):
        self.action, self.payload = "update", data
        return self

    def eq(self, key, val):
        self.predicates.append(("eq", key, val))
        return self

    def gte(self, key, val):
        self.predicates.append(("gte", key, val))
        return self

    def lte(self, key, val):
        self.predicates.append(("lte", key, val))
        return self

    def limit(self, n):
        self.limit_n = n
        return self

    def range(self, a, b):
        self.page = (a, b)
        return self

    def order(self, key):
        self.sort = key
        return self

    def execute(self):
        self.db.calls.append((self.table, self.action, self.predicates[:]))
        if self.db.fail == (self.table, self.action):
            raise ConnectionError("sensitive server response")
        rows = self.db.tables.setdefault(self.table, [])
        def filtered(row):
            for op, col, val in self.predicates:
                v = row.get(col)
                if op == "eq" and v != val:
                    return False
                if op == "gte" and v < val:
                    return False
                if op == "lte" and v > val:
                    return False
            return True
        matches = [row for row in rows if filtered(row)]
        if self.action == "select":
            if self.sort is not None:
                matches.sort(key=lambda r: r[self.sort])
            if self.page is not None:
                a, b = self.page
                matches = matches[a:b + 1]
            if self.limit_n is not None:
                matches = matches[:self.limit_n]
            if self.cols != "*":
                fields = self.cols.split(",")
                matches = [{k: r[k] for k in fields if k in r} for r in matches]
            return Reply(matches)
        if self.action == "insert":
            items = self.payload if isinstance(self.payload, list) else [self.payload]
            rows.extend(items)
            return Reply(items)
        if self.action == "update":
            for row in matches:
                row.update(self.payload)
            return Reply(matches)
        raise AssertionError(self.action)


class Database:
    def __init__(self):
        self.tables = {"users": [{"user_id": "U1", "role": "Magasinier", "actif": "OUI", "hash_mdp": "sensitive"}],
                       "stock_actuel": [{"mp_id": "MP-1", "quantite_disponible": 3}]}
        self.calls = []
        self.fail = None

    def table(self, name):
        return Query(self, name)


@pytest.fixture
def env(monkeypatch):
    db = Database()
    tracker = {"rows": [], "updates": [], "errors": [], "perms": []}
    st = types.ModuleType("streamlit")
    st.cache_resource = lambda fun: fun
    st.session_state = {"authenticated": True, "user": {"user_id": "U1", "role": "ADMIN"}}
    st.secrets = {
        "supabase": {"url": "https://testxyz98765.supabase.co", "key": "dummy"},
        "erp_environment": {
            "name": "TEST",
            "test_supabase_url": "https://testxyz98765.supabase.co",
            "production_supabase_url": "https://prodxyz98765.supabase.co",
            "production_enabled": False,
        },
    }
    supabase = types.ModuleType("supabase")
    supabase.Client = Database
    supabase.create_client = lambda url, key: db
    core = types.ModuleType("core")
    core.__path__ = [str(FILE.parents[1] / "core")]
    sheets = types.ModuleType("core.sheets_service")
    sheets.append_rows_batch = lambda *a: tracker["rows"].append(a)
    sheets.update_multiple_cells_by_id = lambda *a: tracker["updates"].append(a)
    logger = types.ModuleType("core.logger")
    logger.log_error = lambda *a: tracker["errors"].append(a)
    utils = types.ModuleType("core.utils")
    utils.get_local_now = lambda: datetime(2026, 10, 19, 12, 0, 0)
    conf = types.ModuleType("config")
    conf.__path__ = []
    roles = types.ModuleType("config.roles")
    roles.has_permission = lambda *a: tracker["perms"].append(a) or (a in (
        ("Magasinier", "Stocks", "ecriture"),
        ("Magasinier", "Stocks", "lecture"),
    ))
    for name, obj in {"streamlit": st, "supabase": supabase, "core": core,
                      "core.sheets_service": sheets, "core.logger": logger,
                      "core.utils": utils, "config": conf, "config.roles": roles}.items():
        monkeypatch.setitem(sys.modules, name, obj)
    spec = importlib.util.spec_from_file_location("db_module_under_test", FILE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    yield mod, db, st, tracker


def test_valid_permission_db_role_beats_session_role(env):
    module, _, _, trace = env
    assert module.check_server_permission("stock_actuel") is True
    assert trace["perms"][-1] == ("Magasinier", "Stocks", "ecriture")


def test_no_permission_to_other_module(env):
    module, _, _, _ = env
    assert not module.check_server_permission("factures")


def test_inactive_account_denied(env):
    module, db, _, _ = env
    db.tables["users"][0]["actif"] = "NON"
    assert not module.check_server_permission("stock_actuel")


@pytest.mark.parametrize("actif", [None, "", "unknown", False, "non", "0", 0])
def test_inactive_values_denied(env, actif):
    module, db, _, _ = env
    db.tables["users"][0]["actif"] = actif
    assert not module.check_server_permission("stock_actuel")


@pytest.mark.parametrize("actif", ["Oui", True, "1", 1, "ACTIF", "yes"])
def test_active_values_allowed(env, actif):
    module, db, _, _ = env
    db.tables["users"][0]["actif"] = actif
    assert module.check_server_permission("stock_actuel")


def test_invalid_session_denied(env):
    module, _, st, _ = env
    st.session_state["authenticated"] = False
    assert not module.check_server_permission("stock_actuel")
    st.session_state["authenticated"] = True
    st.session_state.pop("user")
    assert not module.check_server_permission("stock_actuel")


def test_missing_or_bad_user_id_denied(env):
    module, _, st, _ = env
    st.session_state["user"] = {"role": "ADMIN"}
    assert not module.check_server_permission("stock_actuel")
    st.session_state["user"] = {"user_id": 20}
    assert not module.check_server_permission("stock_actuel")


def test_user_removed_denied(env):
    module, db, _, _ = env
    db.tables["users"].clear()
    assert not module.check_server_permission("stock_actuel")


def test_admin_db_role_allows_only_known_tables(env):
    module, db, _, _ = env
    db.tables["users"][0]["role"] = "ADMIN"
    assert module.check_server_permission("factures")
    assert not module.check_server_permission("not_an_erp_table")


def test_failure_to_check_account_denies_write(env):
    module, db, _, _ = env
    db.fail = ("users", "select")
    assert not module.check_server_permission("stock_actuel")


def test_unknown_table_rejected_on_insert(env):
    module, db, _, _ = env
    with pytest.raises(PermissionError, match="INSERT direct interdit"):
        module.insert_hybrid("not_present", {"mp_id": "A"})
    assert not any(action == "insert" for _, action, _ in db.calls)


def test_unknown_fields_rejected_on_update(env):
    module, _, _, _ = env
    with pytest.raises(ValueError):
        module.update_hybrid("clients", "client_id", "CLI-1", {"does_not_exist": 1})


def test_empty_update_rejected(env):
    module, _, _, _ = env
    with pytest.raises(ValueError):
        module.update_hybrid("clients", "client_id", "CLI-1", {})


def test_invalid_target_id_and_column_rejected(env):
    module, _, _, _ = env
    with pytest.raises(ValueError, match="primaire"):
        module.update_hybrid("clients", "bad", "CLI-1", {"nom": "test"})
    with pytest.raises(ValueError, match="target_id"):
        module.update_hybrid("clients", "client_id", "", {"nom": "test"})


def test_insert_success_synced_and_audited_without_values(env):
    module, db, _, tracker = env
    db.tables["users"][0]["role"] = "ADMIN"
    payload = {"client_id": "CLI-2", "nom": "Client prive 9"}
    result = module.insert_hybrid("clients", payload)
    assert result == [payload]
    assert len(tracker["rows"]) == 1
    audit = db.tables["audit_trail"][0]
    assert audit["action"] == "INSERT"
    assert "Client prive 9" not in audit["detail"]
    assert "CLI-2" not in audit["detail"]


def test_update_success_and_no_leaky_audit(env):
    module, db, _, tracker = env
    db.tables["users"][0]["role"] = "ADMIN"
    db.tables["clients"] = [{"client_id": "CLI-1", "nom": "Avant"}]
    result = module.update_hybrid("clients", "client_id", "CLI-1", {"nom": "Secret 55"})
    assert result[0]["nom"] == "Secret 55"
    assert tracker["updates"]
    assert "Secret 55" not in db.tables["audit_trail"][0]["detail"]


def test_sensitive_user_never_mirrored_to_sheets(env):
    module, db, _, tracker = env
    db.tables["users"][0]["role"] = "ADMIN"
    data = {"user_id": "U2", "login": "somebody", "hash_mdp": "SUPER_PRIVATE_HASH", "nom": "test"}
    module.insert_hybrid("users", data)
    assert not tracker["rows"]
    assert "SUPER_PRIVATE_HASH" not in repr(db.tables["audit_trail"])


def test_user_update_direct_blocked_even_for_admin(env):
    module, db, _, tracker = env
    db.tables["users"][0]["role"] = "ADMIN"
    with pytest.raises(PermissionError, match="UPDATE direct interdit"):
        module.update_hybrid("users", "user_id", "U1", {"hash_mdp": "NEW_HASH"})
    assert not tracker["updates"]
    assert "NEW_HASH" not in repr(db.tables)
    assert not any(table == "users" and action == "update" for table, action, _ in db.calls)


def test_no_write_when_denied(env):
    module, db, _, tracker = env
    with pytest.raises(PermissionError):
        module.insert_hybrid("factures", {"facture_id": "F1"})
    assert "factures" not in db.tables
    assert not tracker["rows"]


def test_db_write_failure_raises_uncertain_no_sync(env):
    module, db, _, tracker = env
    db.tables["users"][0]["role"] = "ADMIN"
    db.fail = ("clients", "insert")
    with pytest.raises(RuntimeError, match="non confirme"):
        module.insert_hybrid("clients", {"client_id": "CLI-Z"})
    assert not tracker["rows"]
    assert "audit_trail" not in db.tables


def test_sheets_failure_does_not_cancel_supabase_write(env, monkeypatch):
    module, db, _, tracker = env
    db.tables["users"][0]["role"] = "ADMIN"
    monkeypatch.setattr(module, "append_rows_batch", lambda *a: (_ for _ in ()).throw(RuntimeError("secret data")))
    assert module.insert_hybrid("clients", {"client_id": "CLI-Z"})
    assert tracker["errors"]
    assert "secret data" not in repr(tracker["errors"])
    assert db.tables["audit_trail"]


def test_audit_failure_does_not_cancel_write(env):
    module, db, _, _ = env
    db.tables["users"][0]["role"] = "ADMIN"
    db.fail = ("audit_trail", "insert")
    assert module.insert_hybrid("clients", {"client_id": "CLI-Z"})
    assert any(row["client_id"] == "CLI-Z" for row in db.tables["clients"])


def test_update_missing_is_uncertain_and_no_sync(env):
    module, db, _, tracker = env
    db.tables["users"][0]["role"] = "ADMIN"
    with pytest.raises(RuntimeError, match="non verifiable"):
        module.update_hybrid("clients", "client_id", "not-found", {"nom": "Client test"})
    assert not tracker["updates"]
    assert "audit_trail" not in db.tables


def test_reads_existing_signatures(env):
    module, db, _, _ = env
    db.tables["mouvements"] = [{"mouvement_id": "a", "date": "2026-10-18"},
                              {"mouvement_id": "b", "date": "2026-10-20"}]
    assert module.fetch_data("mouvements") == db.tables["mouvements"]
    assert len(module.fetch_data_filtered("mouvements", "mouvement_id", "a")) == 1
    assert len(module.fetch_data_by_date_range("mouvements", "date", "2026-10-19", "2026-10-21")) == 1


def test_read_failure_stays_legacy_empty_list(env):
    module, db, _, tracker = env
    db.fail = ("mouvements", "select")
    assert module.fetch_data("mouvements") == []
    assert tracker["errors"]


def test_pagination_complete(env):
    module, db, _, _ = env
    db.tables["mouvements"] = [{"mouvement_id": f"M{i:03d}"} for i in range(11)]
    assert len(module.fetch_data_paginated("mouvements", page_size=4, max_rows=15)) == 11


def test_pagination_refuses_truncation(env):
    module, db, _, _ = env
    db.tables["mouvements"] = [{"mouvement_id": f"M{i:03d}"} for i in range(9)]
    with pytest.raises(ValueError, match="trop volumineux"):
        module.fetch_data_paginated("mouvements", page_size=4, max_rows=5)


def test_pagination_invalid_arguments(env):
    module, _, _, _ = env
    with pytest.raises(ValueError):
        module.fetch_data_paginated("mouvements", page_size=1001)
    with pytest.raises(ValueError):
        module.fetch_data_paginated("mouvements", order_column="does_not_exist")


def test_get_client_uses_streamlit_secrets(env):
    module, db, _, _ = env
    assert module.get_supabase_client() is db


def test_missing_username_db_record_denied(env):
    module, db, _, _ = env
    db.tables["users"][0].pop("role")
    assert not module.check_server_permission("stock_actuel")


def test_legacy_audit_details_are_hashed_not_copied(env):
    module, db, _, _ = env
    module.log_action("PASSWORD_CHANGE", "users", "motdepasse=LE_SECRET")
    audit = db.tables["audit_trail"][0]["detail"]
    assert "LE_SECRET" not in audit
    assert audit.startswith("details_masques; sha256=")


def test_pagination_default_order_for_permissions_uses_actual_pk(env):
    module, db, _, _ = env
    db.tables["users"][0]["role"] = "ADMIN"
    db.tables["permissions"] = [{"permission_id": 2, "role": "admin"},
                                 {"permission_id": 1, "role": "admin"}]
    out = module.fetch_data_paginated("permissions", page_size=1)
    assert [x["permission_id"] for x in out] == [1, 2]


def test_logs_table_is_defined_but_direct_insert_blocked(env):
    module, db, _, tracker = env
    db.tables["users"][0]["role"] = "ADMIN"
    assert "logs" in module.SCHEMA_CONFIG
    with pytest.raises(PermissionError, match="INSERT direct interdit"):
        module.insert_hybrid("logs", {"user_id": "U1", "action": "test"})
    assert not tracker["rows"]
    assert "logs" not in db.tables


def test_fake_structured_audit_cannot_inject_secret(env):
    module, db, _, _ = env
    module.log_action("A", "users", "operation=INSERT; table=users; colonnes=[user_id]; password=topsecret")
    assert "topsecret" not in db.tables["audit_trail"][0]["detail"]


# --- Controle des lectures cote serveur ---

@pytest.mark.parametrize("lecteur", [
    lambda m: m.fetch_data("factures"),
    lambda m: m.fetch_data_filtered("factures", "client_id", "C1"),
    lambda m: m.fetch_data_by_date_range("factures", "date", "2026-01-01", "2026-12-31"),
    lambda m: m.fetch_data_paginated("factures"),
])
def test_unauthorized_read_denied_before_target_query(env, lecteur):
    module, db, _, _ = env
    with pytest.raises(PermissionError, match="lecture refuse"):
        lecteur(module)
    assert not any(table == "factures" for table, _, _ in db.calls)


@pytest.mark.parametrize("lecteur", [
    lambda m: m.fetch_data("stock_actuel"),
    lambda m: m.fetch_data_filtered("stock_actuel", "mp_id", "MP-1"),
    lambda m: m.fetch_data_by_date_range("mouvements", "date", "2026-01-01", "2026-12-31"),
    lambda m: m.fetch_data_paginated("stock_actuel"),
])
def test_active_stock_role_read_authorized(env, lecteur):
    module, db, _, trace = env
    lecteur(module)
    assert any(t[2] == "lecture" and t[1] == "Stocks" for t in trace["perms"])
    assert any(table != "users" and action == "select" for table, action, _ in db.calls)


def test_read_rejects_unauthenticated_even_for_admin(env):
    module, db, st, _ = env
    db.tables["users"][0]["role"] = "ADMIN"
    st.session_state["authenticated"] = False
    with pytest.raises(PermissionError):
        module.fetch_data("clients")
    assert not db.calls


def test_read_refuses_inactive_or_missing_account(env):
    module, db, _, _ = env
    db.tables["users"][0]["actif"] = "NON"
    with pytest.raises(PermissionError):
        module.fetch_data("stock_actuel")
    db.tables["users"].clear()
    with pytest.raises(PermissionError):
        module.fetch_data_paginated("stock_actuel")
    assert not any(table == "stock_actuel" for table, _, _ in db.calls)


def test_role_altered_in_session_cannot_grant_read(env):
    module, db, st, _ = env
    st.session_state["user"]["role"] = "ADMIN"
    with pytest.raises(PermissionError):
        module.fetch_data("factures")
    assert not any(table == "factures" for table, _, _ in db.calls)


def test_read_role_is_fetched_fresh_each_time(env):
    module, db, _, _ = env
    with pytest.raises(PermissionError):
        module.fetch_data("factures")
    db.tables["users"][0]["role"] = "ADMIN"
    assert module.fetch_data("factures") == []
    db.tables["users"][0]["actif"] = "NON"
    with pytest.raises(PermissionError):
        module.fetch_data("factures")


def test_read_denied_on_user_db_failure(env):
    module, db, _, _ = env
    db.fail = ("users", "select")
    with pytest.raises(PermissionError):
        module.fetch_data("stock_actuel")
    assert not any(table == "stock_actuel" for table, _, _ in db.calls)


def test_read_denied_on_missing_role_and_permissions_error(env):
    module, db, _, _ = env
    db.tables["users"][0].pop("role")
    with pytest.raises(PermissionError):
        module.fetch_data("stock_actuel")
    db.tables["users"][0]["role"] = "Magasinier"
    module.has_permission = lambda *a: (_ for _ in ()).throw(RuntimeError("private"))
    with pytest.raises(PermissionError):
        module.fetch_data("stock_actuel")


def test_unknown_read_table_rejected_without_target_query(env):
    module, db, _, _ = env
    with pytest.raises(PermissionError):
        module.fetch_data("secret_data")
    assert not db.calls


def test_read_rejects_invalid_filter_and_date_columns(env):
    module, db, _, _ = env
    with pytest.raises(ValueError, match="filtre"):
        module.fetch_data_filtered("stock_actuel", "secret_col", "yes")
    with pytest.raises(ValueError, match="date"):
        module.fetch_data_by_date_range("mouvements", "secret_col", "1", "2")
    assert not any(table != "users" for table, _, _ in db.calls)


def test_shared_clients_read_for_ventes_not_rh(env):
    module, db, _, _ = env
    db.tables["users"][0]["role"] = "Commercial"
    db.tables["clients"] = [{"client_id": "C1", "nom": "Client"}]
    module.has_permission = lambda role, section, operation: (
        role, section, operation) == ("Commercial", "Ventes", "lecture")
    assert module.fetch_data("clients")[0]["client_id"] == "C1"
    with pytest.raises(PermissionError):
        module.fetch_data("fiches_de_paie")
    with pytest.raises(PermissionError):
        module.fetch_data("users")


def test_shared_references_can_be_read_with_non_admin_module(env):
    module, db, _, _ = env
    db.tables["users"][0]["role"] = "Commercial"
    db.tables["listes_reference"] = [{"id": 3, "liste_code": "A"}]
    module.has_permission = lambda role, section, operation: (
        role, section, operation) == ("Commercial", "Ventes", "lecture")
    assert module.fetch_data("listes_reference")[0]["id"] == 3


def test_read_user_projection_omits_password_hash(env):
    module, db, _, _ = env
    db.tables["users"][0]["role"] = "ADMIN"
    assert "hash_mdp" not in module.fetch_data("users")[0]
    assert "hash_mdp" not in module.fetch_data_filtered("users", "user_id", "U1")[0]
    assert "hash_mdp" not in module.fetch_data_paginated("users")[0]
    assert all("hash_mdp" not in row for row in module.fetch_data("users"))
    with pytest.raises(ValueError):
        module.fetch_data_filtered("users", "hash_mdp", "secret")
    with pytest.raises(ValueError):
        module.fetch_data_paginated("users", order_column="hash_mdp")


def test_admin_can_read_audit_but_standard_role_cannot(env):
    module, db, _, _ = env
    with pytest.raises(PermissionError):
        module.fetch_data("audit_trail")
    db.tables["users"][0]["role"] = "ADMIN"
    assert module.fetch_data("audit_trail") == []
