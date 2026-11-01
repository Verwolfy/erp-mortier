"""Read-only NextGen readiness: privacy, fail-closed and missing data."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from modules.admin import nextgen_readiness_service as svc


def product(pid="BOND-C1T"):
    return {"pf_id": pid, "nom": pid, "actif": "OUI"}


def sku(sid="NG-SKU-BOND-C1T-SAC5", pid="BOND-C1T", unit="SAC", **extra):
    row = {"sku_id": sid, "pf_id": pid, "format": unit + " 5",
           "unite_vente": unit, "poids_net": 5, "facteur_conversion": 5,
           "prix_vente_defaut": None, "actif": "OUI"}
    row.update(extra)
    return row


def material(mid="NG-MP-001", **extra):
    row = {"mp_id": mid, "actif": "OUI", "fournisseurs_ids": None}
    row.update(extra)
    return row


_MISSING = object()


def prepare(monkeypatch, products=_MISSING, skus=_MISSING,
            materials=_MISSING, fiscal=_MISSING, manager=True):
    sources = {
        "produits": [product()] if products is _MISSING else products,
        "sku_conditionnement": [sku()] if skus is _MISSING else skus,
        "matieres_premieres": [material()] if materials is _MISSING else materials,
        "erp_sku_fiscalite": [] if fiscal is _MISSING else fiscal,
    }
    gate = MagicMock(return_value="USR-ADMIN")
    if not manager:
        gate.side_effect = PermissionError("denied")
    factory = MagicMock()
    db = factory.return_value
    monkeypatch.setattr(svc, "require_security_manager", gate)
    monkeypatch.setattr(svc, "get_supabase_client", factory)

    def table(name):
        q = MagicMock()
        q.select.return_value = q
        q.eq.return_value = q
        q.range.return_value = q
        q.execute.return_value = SimpleNamespace(data=sources[name])
        return q

    db.table.side_effect = table
    return gate, factory, db


def test_missing_tariff_tax_and_supplier(monkeypatch):
    gate, _, db = prepare(monkeypatch)
    r = svc.lister_blocages_nextgen()
    assert r["produits_actifs"] == 1
    assert r["sku_nextgen_actifs"] == 1
    assert r["sans_tarif"] == 1
    assert r["sans_dossier_fiscal"] == 1
    assert r["matieres_sans_fournisseur"] == 1
    assert r["autorise_facturation"] is False
    assert r["autorise_fabrication"] is False
    gate.assert_called_once_with()
    assert db.table.call_count == 4


def test_missing_product_and_measurements(monkeypatch):
    prepare(monkeypatch, products=[product("PROOF-PU-SEAL"), product("FLOW-SP-HR"), product("PROOF-EPX")],
            skus=[sku("NG-SKU-FLOW-L5", "FLOW-SP-HR", "BIDON", poids_net=None, facteur_conversion=None),
                  sku("NG-SKU-EPX-KIT", "PROOF-EPX", "KIT", poids_net=None, facteur_conversion=None)],
            materials=[])
    r = svc.lister_blocages_nextgen()
    assert r["produits_sans_sku"] == ["PROOF-PU-SEAL"]
    assert r["kits_incomplets"] == 1
    assert r["liquides_sans_conversion"] == 1


def test_fiscal_row_not_automatic_approval(monkeypatch):
    prepare(monkeypatch, fiscal=[{"sku_id": "NG-SKU-BOND-C1T-SAC5", "statut": "VALIDEE"}])
    r = svc.lister_blocages_nextgen()
    assert r["sans_dossier_fiscal"] == 0
    assert r["autorise_facturation"] is False
    assert "vérifier indépendamment" in r["rows"][0]["blocages"]


def test_security_before_client(monkeypatch):
    gate, factory, _ = prepare(monkeypatch, manager=False)
    with pytest.raises(PermissionError):
        svc.lister_blocages_nextgen()
    gate.assert_called_once_with()
    factory.assert_not_called()


@pytest.mark.parametrize("table,data", [
    ("produits", None), ("produits", []),
    ("produits", [product(), product()]),
    ("sku_conditionnement", [sku(), sku()]),
    ("sku_conditionnement", [sku(pid="UNKNOWN")]),
    ("sku_conditionnement", [sku(format="")]),
    ("matieres_premieres", [material(), material()]),
    ("matieres_premieres", [material(actif="NON")]),
    ("erp_sku_fiscalite", [None]),
])
def test_corrupt_data_rejected(monkeypatch, table, data):
    values = {"products": [product()], "skus": [sku()],
              "materials": [material()], "fiscal": []}
    values[{"produits": "products", "sku_conditionnement": "skus",
            "matieres_premieres": "materials", "erp_sku_fiscalite": "fiscal"}[table]] = data
    prepare(monkeypatch, **values)
    with pytest.raises(RuntimeError):
        svc.lister_blocages_nextgen()


def test_truncation_rejected(monkeypatch):
    prepare(monkeypatch, products=[product(f"BOND-{i}") for i in range(201)])
    with pytest.raises(RuntimeError):
        svc.lister_blocages_nextgen()


def test_outage_fails_closed(monkeypatch):
    _, _, db = prepare(monkeypatch)
    db.table.side_effect = ConnectionError("offline")
    with pytest.raises(ConnectionError):
        svc.lister_blocages_nextgen()


def test_ui_uses_security_gate_and_no_mutations():
    from pathlib import Path
    view = (Path(__file__).resolve().parents[1] / "modules/admin/views.py").read_text(encoding="utf-8")
    block = view.split("def _revue_nextgen_preparation()", 1)[1].split("\ndef ", 1)[0]
    assert "is_security_manager()" in block and "lister_blocages_nextgen()" in block
    assert not any(word in block for word in ("insert_hybrid(", "update_hybrid(", ".insert(", ".update(", "form_submit_button("))
