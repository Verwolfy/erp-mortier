"""Tests du registre TVA privé (sans appel réel à Supabase)."""
from unittest.mock import MagicMock

import pytest
from modules.admin import exonerations_service as service


def prepare(monkeypatch, entetes, portees, *, autorise=True):
    gate = MagicMock(return_value="USR-ADMIN")
    if not autorise:
        gate.side_effect = PermissionError("Manager requis")
    db = MagicMock()
    client = MagicMock(return_value=db)
    monkeypatch.setattr(service, "require_security_manager", gate)
    monkeypatch.setattr(service, "get_supabase_client", client)

    def table(name):
        obj = MagicMock()
        if name == "erp_exonerations_tva_clients":
            obj.select.return_value.order.return_value.range.return_value.execute.return_value.data = entetes
        elif name == "erp_exonerations_tva_skus":
            obj.select.return_value.order.return_value.range.return_value.execute.return_value.data = portees
        else:
            raise AssertionError("Table imprévue")
        return obj

    db.table.side_effect = table
    return gate, client, db


def attestation(id="AT-1"):
    return {
        "attestation_id": id,
        "client_id": "CLI-TEST",
        "reference_attestation": "DOC-TEST",
        "statut": "A_VALIDER",
    }


def test_refus_si_security_manager_non_confirme(monkeypatch):
    gate, client, db = prepare(monkeypatch, [], [], autorise=False)
    with pytest.raises(PermissionError):
        service.lister_attestations_pour_manager()
    gate.assert_called_once_with()
    client.assert_not_called()
    db.table.assert_not_called()


def test_tableau_regroupe_attestation_et_nombre_skus(monkeypatch):
    source = [attestation("AT-1"), attestation("AT-2")]
    gate, client, db = prepare(
        monkeypatch, source,
        [{"attestation_id": "AT-1", "sku_id": "SKU-A"},
         {"attestation_id": "AT-1", "sku_id": "SKU-B"}],
    )
    rows = service.lister_attestations_pour_manager()
    assert [r["nombre_sku_couverts"] for r in rows] == [2, 0]
    assert rows[0]["statut"] == "A_VALIDER"
    gate.assert_called_once_with()
    assert db.table.call_count == 2
    for call in db.table.call_args_list:
        assert call.args[0] in {
            "erp_exonerations_tva_clients", "erp_exonerations_tva_skus"
        }


def test_registre_vide_retourne_aucun_dossier(monkeypatch):
    _, _, db = prepare(monkeypatch, [], [])
    assert service.lister_attestations_pour_manager() == []
    db.table.assert_called_once_with("erp_exonerations_tva_clients")


@pytest.mark.parametrize("entetes,portees", [
    (None, []),
    ([None], []),
    ([attestation("AT-1"), attestation("AT-1")], []),
    ([attestation("AT-1")], None),
    ([attestation("AT-1")], [{"attestation_id": "AT-2", "sku_id": "SKU-X"}]),
    ([attestation("AT-1")], [{"attestation_id": "AT-1", "sku_id": ""}]),
    ([attestation("AT-1")], [None]),
])
def test_resultats_incomplets_refuses(monkeypatch, entetes, portees):
    prepare(monkeypatch, entetes, portees)
    with pytest.raises(RuntimeError):
        service.lister_attestations_pour_manager()


def test_limite_bloque_pagination_tronquee(monkeypatch):
    prepare(monkeypatch, [attestation("AT-%d" % i) for i in range(501)], [])
    with pytest.raises(RuntimeError, match="incomplète"):
        service.lister_attestations_pour_manager()
