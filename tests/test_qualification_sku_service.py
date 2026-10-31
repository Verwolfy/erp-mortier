"""Contrôle de la revue SKU : lecture seule, accès privé, aucune TVA implicite."""
from unittest.mock import MagicMock

import pytest

from modules.admin import qualification_sku_service as service


def sku(sku_id="SKU-001", **modifications):
    row = {
        "sku_id": sku_id, "pf_id": "PF-001", "format": "Sac 25kg",
        "unite_vente": "SAC", "actif": "OUI",
    }
    row.update(modifications)
    return row


def prepare(monkeypatch, sku_rows, fiscal_rows, *, manager=True):
    gate = MagicMock(return_value="USR-ADMIN")
    if not manager:
        gate.side_effect = PermissionError("Droit refusé")
    db = MagicMock()
    factory = MagicMock(return_value=db)
    monkeypatch.setattr(service, "require_security_manager", gate)
    monkeypatch.setattr(service, "get_supabase_client", factory)

    def table(name):
        q = MagicMock()
        if name == "sku_conditionnement":
            q.select.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value.data = sku_rows
        elif name == "erp_sku_fiscalite":
            q.select.return_value.order.return_value.range.return_value.execute.return_value.data = fiscal_rows
        else:
            raise AssertionError("Table non prévue")
        return q

    db.table.side_effect = table
    return gate, factory, db


def test_catalogue_reel_sans_classement_ne_presume_aucun_taux(monkeypatch):
    gate, _, db = prepare(monkeypatch, [sku("SKU-001"), sku("SKU-002")], [])
    result = service.lister_sku_a_qualifier()
    assert result["sku_actifs"] == 2
    assert result["sku_sans_dossier"] == 2
    assert result["sku_avec_dossier"] == 0
    assert result["autorise_activation_facturation"] is False
    assert [r["etat_revue"] for r in result["rows"]] == ["À qualifier"] * 2
    assert all("taux_tva" not in r and "categorie_tva" not in r for r in result["rows"])
    gate.assert_called_once_with()
    assert [c.args[0] for c in db.table.call_args_list] == [
        "sku_conditionnement", "erp_sku_fiscalite",
    ]


def test_dossier_existant_exige_revue_sans_approbation_automatique(monkeypatch):
    prepare(monkeypatch, [sku()], [{"sku_id": "SKU-001", "statut": "VALIDEE"}])
    result = service.lister_sku_a_qualifier()
    assert result["sku_sans_dossier"] == 0
    assert result["sku_avec_dossier"] == 1
    assert "vérification indépendante" in result["rows"][0]["etat_revue"]
    assert result["autorise_activation_facturation"] is False


def test_securite_verifiee_avant_consultation(monkeypatch):
    gate, factory, _ = prepare(monkeypatch, [], [], manager=False)
    with pytest.raises(PermissionError):
        service.lister_sku_a_qualifier()
    gate.assert_called_once_with()
    factory.assert_not_called()


@pytest.mark.parametrize("catalogue,fiscal", [
    (None, []),
    ([None], []),
    ([sku("SKU-001"), sku("SKU-001")], []),
    ([sku("SKU-001", actif="NON")], []),
    ([sku("SKU-001", format="")], []),
    ([], None),
    ([], [None]),
    ([sku()], [{"sku_id": "SKU-001", "statut": ""}]),
    ([sku()], [{"sku_id": None, "statut": "VALIDEE"}]),
    ([sku("SKU-%04d" % i) for i in range(501)], []),
    ([], [{"sku_id": "SKU-X", "statut": "VALIDEE"} for _ in range(2001)]),
])
def test_referentiels_ambigus_refuses(monkeypatch, catalogue, fiscal):
    prepare(monkeypatch, catalogue, fiscal)
    with pytest.raises(RuntimeError):
        service.lister_sku_a_qualifier()


def test_lecture_reseau_refuse_au_lieu_de_simuler_des_skus(monkeypatch):
    _, _, db = prepare(monkeypatch, [sku()], [])
    db.table.side_effect = ConnectionError("DB indisponible")
    with pytest.raises(ConnectionError):
        service.lister_sku_a_qualifier()
