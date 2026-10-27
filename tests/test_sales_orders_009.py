from types import SimpleNamespace

import pytest
from modules.ventes import service as sales


@pytest.fixture
def fake_rpc(monkeypatch):
    calls = []

    class Client:
        fail = False
        override = None

        def rpc(self, name, args):
            calls.append((name, args))
            return self

        def execute(self):
            if self.fail:
                raise ConnectionError("Simulated timeout")
            op_id = calls[-1][1]["p_operation_id"]
            data = self.override
            if data is None:
                data = {
                    "operation_id": op_id,
                    "commande_vente_id": "CDV-0001",
                    "statut": "EN_ATTENTE",
                }
            return SimpleNamespace(data=data)

    client = Client()
    monkeypatch.setattr(
        sales, "check_server_permission", lambda name: True
    )
    monkeypatch.setattr(
        sales, "_stock_rpc_client", lambda: client
    )
    return client, calls


def valid_lines():
    return [{
        "sku_id": "SKU-001",
        "quantite": 1,
        "prix_unitaire": "1250.00",
    }]


def test_order_creation_uses_atomic_rpc(fake_rpc):
    client, calls = fake_rpc
    result = sales.creer_commande_client(
        "CLI-0007", "2026-10-24", valid_lines(),
        operation_id="TEST-ORDER-009",
    )
    assert result == "CDV-0001"
    assert len(calls) == 1
    name, args = calls[0]
    assert name == "erp_create_sales_order"
    assert args["p_operation_id"] == "TEST-ORDER-009"
    assert args["p_client_id"] == "CLI-0007"
    assert args["p_lignes"][0]["quantite"] == "1"


def test_order_denied_without_permission(fake_rpc, monkeypatch):
    client, calls = fake_rpc
    monkeypatch.setattr(
        sales, "check_server_permission", lambda name: False
    )
    with pytest.raises(PermissionError):
        sales.creer_commande_client(
            "CLI-0007", "2026-10-24", valid_lines()
        )
    assert calls == []


@pytest.mark.parametrize("quantity", [
    0, -1, "1.5", "NaN", True
])
def test_invalid_quantity_is_rejected(fake_rpc, quantity):
    client, calls = fake_rpc
    lines = valid_lines()
    lines[0]["quantite"] = quantity
    with pytest.raises(ValueError):
        sales.creer_commande_client(
            "CLI-0007", "2026-10-24", lines
        )
    assert calls == []


def test_duplicate_sku_is_rejected(fake_rpc):
    client, calls = fake_rpc
    with pytest.raises(ValueError):
        sales.creer_commande_client(
            "CLI-0007", "2026-10-24",
            valid_lines() + valid_lines()
        )
    assert calls == []


def test_price_precision_is_checked(fake_rpc):
    client, calls = fake_rpc
    lines = valid_lines()
    lines[0]["prix_unitaire"] = "1250.123"
    with pytest.raises(ValueError):
        sales.creer_commande_client(
            "CLI-0007", "2026-10-24", lines
        )
    assert calls == []


def test_timeout_preserves_operation_id(fake_rpc):
    client, calls = fake_rpc
    client.fail = True
    with pytest.raises(sales.SaleOperationError) as exc:
        sales.creer_commande_client(
            "CLI-0007", "2026-10-24", valid_lines(),
            operation_id="TEST-RETRY-009",
        )
    assert exc.value.operation_id == "TEST-RETRY-009"
    assert len(calls) == 1


def test_unverifiable_response_is_rejected(fake_rpc):
    client, calls = fake_rpc
    client.override = {
        "operation_id": "OTHER-OPERATION",
        "commande_vente_id": "CDV-0001",
        "statut": "EN_ATTENTE",
    }
    with pytest.raises(sales.SaleOperationError):
        sales.creer_commande_client(
            "CLI-0007", "2026-10-24", valid_lines(),
            operation_id="TEST-RESPONSE-009",
        )
