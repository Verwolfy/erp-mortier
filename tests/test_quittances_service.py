"""Contrats sans réseau du service d'accusé d'encaissement interne."""
from unittest.mock import MagicMock
import pytest

from modules.finance import quittances_service as s


@pytest.fixture
def fake(monkeypatch):
    rpc = MagicMock()
    client = MagicMock()
    client.rpc.return_value = rpc
    rpc.execute.return_value.data = {
        "recu_id": "RINT-00000000-0000-4000-8000-000000000001",
        "reglement_id": "REG-1",
        "operation_id": "RECUI-12345678",
        "statut": "INTERNE_NON_FISCAL",
        "timbre_statut": "NON_CALCULE",
    }
    allowed = MagicMock(return_value=True)
    monkeypatch.setattr(s, "check_server_permission", allowed)
    monkeypatch.setattr(s, "_stock_rpc_client", lambda: client)
    return allowed, client, rpc


def test_une_transaction_rpc_et_aucun_timbre(fake):
    permission, db, _ = fake
    output = s.emettre_recu_interne("REG-1", operation_id="RECUI-12345678")
    assert output["recu_id"].startswith("RINT-")
    assert output["timbre_statut"] == "NON_CALCULE"
    permission.assert_called_once_with("reglements")
    db.rpc.assert_called_once_with("erp_emettre_recu_interne", {
        "p_operation_id": "RECUI-12345678", "p_reglement_id": "REG-1"
    })


def test_droit_refuse_avant_rpc(fake):
    permission, db, _ = fake
    permission.return_value = False
    with pytest.raises(PermissionError):
        s.emettre_recu_interne("REG-1", operation_id="RECUI-12345678")
    db.rpc.assert_not_called()


@pytest.mark.parametrize("ident", ["", "   ", "X"*201, None])
def test_identifiant_paiement_invalide(fake, ident):
    _, db, _ = fake
    with pytest.raises(ValueError):
        s.emettre_recu_interne(ident)
    db.rpc.assert_not_called()


@pytest.mark.parametrize("op", ["RECUI-1","RECUI-12345678!","FIN-UI-12345678"," "*20])
def test_operation_id_non_valide(fake, op):
    _, db, _ = fake
    with pytest.raises(ValueError):
        s.emettre_recu_interne("REG-1", operation_id=op)
    db.rpc.assert_not_called()


def test_timeout_garde_operation_id_sans_creer_doublon(fake):
    _,db,rpc=fake
    rpc.execute.side_effect=RuntimeError("network timeout")
    with pytest.raises(s.RecuOperationIncertaine) as error:
        s.emettre_recu_interne("REG-1", operation_id="RECUI-12345678")
    assert error.value.operation_id=="RECUI-12345678"
    assert "network timeout" not in str(error.value)


def test_reponse_non_concordante_indeterminee(fake):
    _,_,rpc=fake
    rpc.execute.return_value.data={"recu_id":"RINT-X", "operation_id":"ANOTHER"}
    with pytest.raises(s.RecuOperationIncertaine) as exc:
        s.emettre_recu_interne("REG-1", operation_id="RECUI-12345678")
    assert exc.value.operation_id=="RECUI-12345678"
