"""ERP-056 : inventaire métier testé sans réseau ni mouvement réel."""
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from modules.stocks import inventory_service as inv


@pytest.mark.parametrize("bad", ["", "-1", "NaN", "Infinity", "-Infinity",
                                 "1000000000000000", True, None])
def test_inventory_rejects_invalid_physical_quantity(bad):
    with pytest.raises(ValueError):
        inv._valid_quantity(bad)


def test_inventory_accepts_zero_and_fractional_physical_counts():
    assert inv._valid_quantity(0) == "0"
    assert inv._valid_quantity("0.125") == "0.125"


def test_inventory_summary_keeps_unpriced_deltas_unvalued():
    rows = [
        {"quantite_theorique": "10", "quantite_comptee": "8",
         "pmp_snapshot": "20"},
        {"quantite_theorique": "3", "quantite_comptee": "5",
         "pmp_snapshot": None},
        {"quantite_theorique": "7", "quantite_comptee": None,
         "pmp_snapshot": "10"},
    ]
    result = inv.summarize_inventory(rows)
    assert result == {
        "lignes": 3, "comptees": 2, "ecarts": 2,
        "ecarts_sans_pmp": 1, "valeur_ecart_dzd": None,
    }


def test_inventory_summary_of_priced_deltas():
    result = inv.summarize_inventory([
        {"quantite_theorique": "10", "quantite_comptee": "12",
         "pmp_snapshot": "100.5"},
        {"quantite_theorique": "9", "quantite_comptee": "6",
         "pmp_snapshot": "10"},
    ])
    assert Decimal(result["valeur_ecart_dzd"]) == Decimal("171.0")


def test_no_session_cannot_read_or_mutate(monkeypatch):
    monkeypatch.setattr(inv.st, "session_state", {"authenticated": False})
    called = MagicMock()
    monkeypatch.setattr(inv, "get_supabase_client", called)
    with pytest.raises(PermissionError):
        inv.list_inventories()
    with pytest.raises(PermissionError):
        inv.submit_inventory("INV-TEST-12345678")
    called.assert_not_called()


def _authenticated(monkeypatch, role="MAGASINIER", enabled="OUI"):
    monkeypatch.setattr(inv.st, "session_state", {
        "authenticated": True, "user": {"user_id": "USER-X", "role": "ADMIN"}
    })
    client = MagicMock()
    query = (client.table.return_value.select.return_value.eq.return_value
             .limit.return_value)
    query.execute.return_value = SimpleNamespace(data=[{
        "user_id": "USER-X", "role": role, "actif": enabled
    }])
    monkeypatch.setattr(inv, "get_supabase_client", lambda: client)
    monkeypatch.setattr(inv, "has_permission",
                        lambda r, module, action: r == role and module == "Stocks")
    return client


def test_identity_uses_fresh_database_role_not_session_admin(monkeypatch):
    client = _authenticated(monkeypatch, role="MAGASINIER")
    assert inv._identity(writing=True) == ("USER-X", "MAGASINIER")
    with pytest.raises(PermissionError):
        inv._identity(writing=True, approving=True)
    assert client.table.called


def test_inactive_identity_is_denied_even_with_session_admin(monkeypatch):
    _authenticated(monkeypatch, role="ADMIN", enabled="NON")
    with pytest.raises(PermissionError):
        inv._identity(writing=True)


def test_create_campaign_uses_stable_id_and_validated_actor(monkeypatch):
    client = _authenticated(monkeypatch, role="MAGASINIER")
    response = SimpleNamespace(data={
        "inventaire_id": "INV-TEST-12345678", "statut": "OUVERT", "lignes": 7
    })
    client.rpc.return_value.execute.return_value = response
    result = inv.create_inventory("MP", "Inventaire de contrôle",
                                  campaign_id="INV-TEST-12345678")
    assert result["lignes"] == 7
    args, kwargs = client.rpc.call_args
    assert args[0] == "erp_inventory_create"
    assert args[1]["p_acteur_id"] == "USER-X"
    assert args[1]["p_inventaire_id"] == "INV-TEST-12345678"


def test_failed_rpc_does_not_invent_confirmation(monkeypatch):
    client = _authenticated(monkeypatch, role="ADMIN")
    client.rpc.return_value.execute.side_effect = TimeoutError("network")
    with pytest.raises(inv.InventoryError, match="non confirmée"):
        inv.count_article("INV-TEST-12345678", "MP", "MP-01", "0", "Compté")
    client.rpc.return_value.execute.side_effect = None
    client.rpc.return_value.execute.return_value = SimpleNamespace(data={"other": True})
    with pytest.raises(inv.InventoryError, match="non confirmé"):
        inv.submit_inventory("INV-TEST-12345678")


def test_inventory_approval_requires_admin_and_justification(monkeypatch):
    client = _authenticated(monkeypatch, role="ADMIN")
    client.rpc.return_value.execute.return_value = SimpleNamespace(
        data={"inventaire_id": "INV-TEST-12345678", "statut": "ECARTS_A_QUALIFIER"}
    )
    with pytest.raises(ValueError):
        inv.approve_inventory("INV-TEST-12345678", "ok")
    result = inv.approve_inventory(
        "INV-TEST-12345678", "Constat validé, écarts à qualifier"
    )
    assert result["statut"] == "ECARTS_A_QUALIFIER"
    assert client.rpc.call_args.args[1]["p_acteur_id"] == "USER-X"


def test_sql_migration_never_updates_live_stock_directly():
    sql = (Path(__file__).resolve().parents[1] /
           "sql/ERP_056_inventaire_physique_campagne_20261120.sql"
           ).read_text(encoding="utf-8")
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "REVOKE ALL ON public.erp_inventaires" in sql
    assert "mouvements_stock_appliques',false" in sql
    assert "erp_apply_stock_movement(" not in sql
    assert "UPDATE public.stock_actuel " not in sql
    assert "UPDATE public.stock_actuel_pf " not in sql
    assert "createur_id=p_acteur_id" in sql
    assert "v_inv.soumis_par=p_acteur_id" in sql


def test_inventory_view_is_loaded_only_on_requested_panel():
    source = (Path(__file__).resolve().parents[1] /
              "modules/stocks/views.py").read_text(encoding="utf-8")
    assert "if active_panel == panels[4]:" in source
    assert "from modules.stocks.inventory_views import show_inventory_panel" in source
