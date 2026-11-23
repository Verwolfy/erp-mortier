"""ERP-062 : les demandes Achat et la conversion BC restent sûres et désactivées par défaut."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modules.achats import requisitions as req

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def access(monkeypatch):
    monkeypatch.setattr(req, "check_server_permission", lambda table: table == "commandes_achats")
    monkeypatch.setattr(req, "check_server_read_permission", lambda table: table == "commandes_achats")
    monkeypatch.setattr(req.st, "session_state", {
        "authenticated": True, "user": {"user_id": "US-ERP62"},
    })
    mock = MagicMock()
    monkeypatch.setattr(req, "_stock_rpc_client", lambda: mock)
    return mock


def test_da_requires_motivation_date_and_unique_positive_materials():
    payload = req.create_request_payload(
        "Nécessité documentée en service logistique", "2026-12-15",
        [{"mp_id": "MP-1", "quantite": "3.5"}],
    )
    assert payload["lignes"] == [{"mp_id": "MP-1", "quantite": "3.5"}]
    with pytest.raises(ValueError):
        req.create_request_payload("court", "2026-12-15",
                                   [{"mp_id": "MP-1", "quantite": 2}])
    with pytest.raises(ValueError):
        req.create_request_payload("Explication suffisante", "2026-02-30",
                                   [{"mp_id": "MP-1", "quantite": 2}])
    with pytest.raises(ValueError):
        req.create_request_payload("Explication suffisante", "2026-12-15",
                                   [{"mp_id": "MP-1", "quantite": 2},
                                    {"mp_id": "MP-1", "quantite": 4}])
    with pytest.raises(ValueError):
        req.create_request_payload("Explication suffisante", "2026-12-15",
                                   [{"mp_id": "MP-1", "quantite": "-1"}])


def test_po_conversion_locks_dzd_and_validates_prices():
    payload = req.convert_request_payload(
        "DA-1", "FOU-1", [{"mp_id": "MP-1", "quantite": 4,
                          "prix_unitaire": "150.25"}], "2026-12-15")
    assert payload["devise"] == "DZD"
    assert payload["taux_change"] == 1
    assert payload["lignes"][0]["prix_unitaire"] == "150.25"
    with pytest.raises(ValueError):
        req.convert_request_payload(
            "DA-1", "FOU-1", [{"mp_id": "MP-1", "quantite": 4,
                              "prix_unitaire": "-1"}], "2026-12-15")


def test_all_actions_use_one_server_rpc_and_current_actor(access):
    access.rpc.return_value.execute.return_value.data = {
        "operation_id": "DA-UI-OP1", "demande_id": "DA-TEST", "statut": "SOUMISE",
    }
    result = req.purchase_request_action(
        "SUBMIT", {"demande_id": "DA-TEST"}, operation_id="DA-UI-OP1")
    assert result["demande_id"] == "DA-TEST"
    name, args = access.rpc.call_args.args
    assert name == "erp_purchase_request_transaction"
    assert args["p_acteur_id"] == "US-ERP62"
    assert args["p_operation_id"] == "DA-UI-OP1"


def test_missing_permission_or_session_rejects_before_rpc(access, monkeypatch):
    monkeypatch.setattr(req, "check_server_permission", lambda table: False)
    with pytest.raises(PermissionError):
        req.purchase_request_action("APPROVE", {"demande_id": "DA-1"},
                                    operation_id="DA-UI-OP1")
    access.rpc.assert_not_called()


def test_rpc_timeout_preserves_original_operation_id(access):
    access.rpc.return_value.execute.side_effect = TimeoutError("PostgREST timeout")
    with pytest.raises(req.PurchaseRequestError) as exc:
        req.purchase_request_action("SUBMIT", {"demande_id": "DA-1"},
                                    operation_id="DA-UI-REPLAY")
    assert exc.value.operation_id == "DA-UI-REPLAY"
    assert access.rpc.call_args.args[1]["p_operation_id"] == "DA-UI-REPLAY"


def test_malformed_success_response_not_accepted(access):
    access.rpc.return_value.execute.return_value.data = {
        "operation_id": "DIFFERENT", "demande_id": "DA-1", "statut": "APPROUVEE"
    }
    with pytest.raises(req.PurchaseRequestError):
        req.purchase_request_action("APPROVE", {"demande_id": "DA-1"},
                                    operation_id="DA-UI-OP1")


def test_da_sql_acl_rbac_separation_and_idempotency():
    source = (ROOT / "sql/ERP_062_PREPARATION_demandes_achats_20261123.sql").read_text()
    for table in ("erp_purchase_requests", "erp_purchase_request_lines",
                  "erp_purchase_request_operations", "erp_purchase_request_events"):
        assert f"public.{table} ENABLE ROW LEVEL SECURITY" in source
    assert "SECURITY INVOKER" in source
    assert "FROM PUBLIC,anon,authenticated" in source
    assert "TO service_role" in source
    assert "v_da.demandeur_id=p_acteur_id" in source
    assert "v_da.approbateur_id IS NULL" in source
    assert "v_actual IS DISTINCT FROM v_approved" in source
    assert "v_saved.request_payload IS DISTINCT FROM p_payload" in source
    assert "public.erp_create_purchase_order(" in source
    assert "public.erp_apply_stock_movement(" not in source
    assert "public.erp_finance_transaction(" not in source


def test_da_ui_hidden_by_default_and_existing_po_form_blocked_when_enabled():
    source = (ROOT / "modules/achats/views.py").read_text()
    assert 'os.environ.get("ERP_PURCHASE_REQUESTS_ENABLED") == "1"' in source
    assert 'if demandes_actives and active_panel == panels[0]:' in source
    assert 'if demandes_actives and active_panel == panels[3]:' in source
