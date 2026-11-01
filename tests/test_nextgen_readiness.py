"""Read-only NextGen readiness: privacy, fail-closed and missing data."""
import csv
from io import StringIO
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
            materials=_MISSING, fiscal=_MISSING, manager=True, cap=None):
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
        filters, order_keys = {}, []
        def eq(field, value):
            filters[field] = value
            return q
        def order(key):
            order_keys.append(key)
            return q
        def page(start, end):
            all_rows = sources[name]
            if not isinstance(all_rows, list):
                q.execute.return_value = SimpleNamespace(data=all_rows, count=None)
                return q
            # Keep malformed entries so the service, not the fixture, rejects them.
            filtered = [row for row in all_rows if not filters or (
                isinstance(row, dict) and
                all(row.get(field) == value for field, value in filters.items()))]
            data = sorted(filtered, key=lambda row: tuple(
                str(row.get(key, "")) if isinstance(row, dict) else "" for key in order_keys
            ))
            batch = data[start:end + 1]
            if cap is not None:
                batch = batch[:cap]  # simulate PostgREST lower server-side row cap
            q.execute.return_value = SimpleNamespace(data=batch, count=len(data))
            return q
        q.eq.side_effect = eq
        q.order.side_effect = order
        q.range.side_effect = page
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
    assert gate.call_count == 5  # initial gate + one gate per table/page
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
    prepare(monkeypatch, fiscal=[{"sku_id": "NG-SKU-BOND-C1T-SAC5", "date_effet": "2026-01-01", "statut": "VALIDEE"}])
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


def test_export_nextgen_register_csv(monkeypatch):
    gate, _, _ = prepare(monkeypatch)
    inventory = svc.lister_blocages_nextgen()
    export = svc.exporter_registre_nextgen_csv(inventory)
    rows = list(csv.reader(StringIO(export.lstrip("\ufeff")), delimiter=";"))
    assert export.startswith("\ufeff")
    assert rows[0] == [
        "sku_id", "pf_id", "format", "unite_vente", "blocages",
        "reference_preuve_a_completer", "statut_qualification",
    ]
    assert rows[1][0] == "NG-SKU-BOND-C1T-SAC5"
    assert "Tarif absent" in rows[1][4]
    assert rows[1][-2:] == ["", "NON_VERIFIE"]
    assert len(rows) == 2
    assert "telephone" not in export and "prix_vente_defaut" not in export
    assert gate.call_count == 6  # initial + each of four pages + export


def test_export_escapes_spreadsheet_formula(monkeypatch):
    prepare(monkeypatch)
    inventory = svc.lister_blocages_nextgen()
    inventory["rows"][0]["format"] = "  =HYPERLINK(1,2)"
    rows = list(csv.reader(StringIO(svc.exporter_registre_nextgen_csv(inventory).lstrip("\ufeff")), delimiter=";"))
    assert rows[1][2].startswith("'  =HYPERLINK")


@pytest.mark.parametrize("tamper", [
    lambda r: r.update(autorise_facturation=True),
    lambda r: r.update(autorise_fabrication=None),
    lambda r: r.update(rows=None),
    lambda r: r["rows"][0].update(telephone="confidentiel"),
    lambda r: r["rows"][0].update(sku_id=""),
    lambda r: r["rows"][0].update(format=123),
    lambda r: r.update(rows=r["rows"] * (svc.LIMITS["sku_conditionnement"] + 1)),
])
def test_export_rejects_invalid_or_unapproved_snapshot(monkeypatch, tamper):
    prepare(monkeypatch)
    inventory = svc.lister_blocages_nextgen()
    tamper(inventory)
    with pytest.raises(ValueError):
        svc.exporter_registre_nextgen_csv(inventory)


def test_export_never_bypasses_security_gate(monkeypatch):
    prepare(monkeypatch)
    inventory = svc.lister_blocages_nextgen()
    prepare(monkeypatch, manager=False)
    with pytest.raises(PermissionError):
        svc.exporter_registre_nextgen_csv(inventory)


def test_ui_export_is_readonly_and_gated():
    from pathlib import Path
    view = (Path(__file__).resolve().parents[1] / "modules/admin/views.py").read_text(encoding="utf-8")
    block = view.split("def _revue_nextgen_preparation()", 1)[1].split("\ndef ", 1)[0]
    assert "is_security_manager()" in block
    assert "exporter_registre_nextgen_csv(result)" in block
    assert "st.download_button(" in block
    assert not any(word in block for word in (".insert(", ".update(", ".delete(", "insert_hybrid(", "update_hybrid("))


def test_all_skus_loaded_with_backend_cap(monkeypatch):
    records = [sku(f"NG-SKU-{i:04d}") for i in range(142)]
    gate, _, db = prepare(monkeypatch, skus=records, cap=17)
    result = svc.lister_blocages_nextgen()
    assert result["sku_nextgen_actifs"] == 142
    assert result["sans_tarif"] == 142
    assert len(result["rows"]) == 142
    assert len({row["sku_id"] for row in result["rows"]}) == 142
    # 1 product + 9 SKU pages + 1 material + 1 empty fiscal page
    assert db.table.call_count == 12
    assert gate.call_count == 13


def test_composite_fiscal_key_accepts_successive_dates(monkeypatch):
    two_versions = [
        {"sku_id": "NG-SKU-BOND-C1T-SAC5", "date_effet": "2025-01-01", "statut": "A_CONFIRMER"},
        {"sku_id": "NG-SKU-BOND-C1T-SAC5", "date_effet": "2026-01-01", "statut": "VALIDEE"},
    ]
    prepare(monkeypatch, fiscal=two_versions, cap=1)
    result = svc.lister_blocages_nextgen()
    assert result["sans_dossier_fiscal"] == 0
    assert result["autorise_facturation"] is False
    assert result["autorise_fabrication"] is False


def test_duplicate_composite_fiscal_key_rejected(monkeypatch):
    record = {"sku_id": "NG-SKU-BOND-C1T-SAC5", "date_effet": "2026-01-01", "statut": "A_CONFIRMER"}
    prepare(monkeypatch, fiscal=[record, dict(record)], cap=1)
    with pytest.raises(RuntimeError, match="répété"):
        svc.lister_blocages_nextgen()


def test_missing_exact_count_rejected(monkeypatch):
    _, _, db = prepare(monkeypatch)
    original = db.table.side_effect

    def table_without_count(name):
        q = original(name)
        if name == "sku_conditionnement":
            page = q.range.side_effect
            def no_count(start, end):
                page(start, end)
                q.execute.return_value.count = None
                return q
            q.range.side_effect = no_count
        return q

    db.table.side_effect = table_without_count
    with pytest.raises(RuntimeError, match="incomplet"):
        svc.lister_blocages_nextgen()


def test_count_drift_across_pages_rejected(monkeypatch):
    records = [sku(f"NG-SKU-{i:04d}") for i in range(108)]
    _, _, db = prepare(monkeypatch, skus=records)
    original = db.table.side_effect

    def table_with_drift(name):
        q = original(name)
        if name == "sku_conditionnement":
            page = q.range.side_effect
            def drift(start, end):
                page(start, end)
                if start:
                    q.execute.return_value.count += 1
                return q
            q.range.side_effect = drift
        return q

    db.table.side_effect = table_with_drift
    with pytest.raises(RuntimeError, match="incohérente"):
        svc.lister_blocages_nextgen()


def test_empty_intermediate_page_rejected(monkeypatch):
    records = [sku(f"NG-SKU-{i:04d}") for i in range(105)]
    _, _, db = prepare(monkeypatch, skus=records)
    original = db.table.side_effect

    def table_with_gap(name):
        q = original(name)
        if name == "sku_conditionnement":
            page = q.range.side_effect
            def gap(start, end):
                page(start, end)
                if start:
                    q.execute.return_value.data = []
                return q
            q.range.side_effect = gap
        return q

    db.table.side_effect = table_with_gap
    with pytest.raises(RuntimeError, match="interrompue"):
        svc.lister_blocages_nextgen()


def test_security_permission_revoked_before_next_page(monkeypatch):
    records = [sku(f"NG-SKU-{i:04d}") for i in range(105)]
    gate, _, db = prepare(monkeypatch, skus=records)
    def check_access():
        if gate.call_count >= 4:
            raise PermissionError("revoked")
    gate.side_effect = check_access
    with pytest.raises(PermissionError, match="revoked"):
        svc.lister_blocages_nextgen()
    # product and first SKU page were queried, but the second was not.
    assert db.table.call_count == 2


def test_all_exact_count_reads_use_stable_keys(monkeypatch):
    _, _, db = prepare(monkeypatch)
    queries = []
    factory = db.table.side_effect
    def tracked_table(name):
        q = factory(name)
        queries.append((name, q))
        return q
    db.table.side_effect = tracked_table
    svc.lister_blocages_nextgen()
    for name, q in queries:
        assert q.select.call_args.kwargs["count"] == "exact"
        assert [call.args[0] for call in q.order.call_args_list] == list(svc.READ_KEYS[name])
