"""Tests fictifs : ventilation de remise, aucun statut fiscal réel."""
from decimal import Decimal
from types import SimpleNamespace

import pytest

from modules.ventes.fiscal_preview import ApercuFiscalIndisponible
from modules.ventes.fiscal_repartition import (
    preparer_assiettes_tva, simuler_tva_panier,
)


def item(sku="SKU-TEST-A", q="1", price="100.00", discount="0.00"):
    return {"sku_id": sku, "quantite": q,
            "prix_unitaire": price, "remise_ligne": discount}


def test_allocation_proportionnelle_et_totaux_au_centime():
    result = preparer_assiettes_tva([
        item(), item("SKU-TEST-B", price="50.00"),
    ], "15.00")
    assert result["total_ht_avant_remise_globale"] == "150.00"
    assert result["remise_globale"] == "15.00"
    assert result["total_ht_apres_remise_globale"] == "135.00"
    assert [x["montant_ht"] for x in result["lignes"]] == ["90.00", "45.00"]
    assert [x["remise_globale_affectee"] for x in result["repartition_remise_globale"]] == ["10.00", "5.00"]


def test_allocation_d_un_centime_a_parts_egales_reproductible():
    r = preparer_assiettes_tva([
        item("A", price="1.00"), item("B", price="1.00"),
        item("C", price="1.00"),
    ], "0.02")
    assert [x["remise_globale_affectee"] for x in r["repartition_remise_globale"]] == ["0.01","0.01","0.00"]
    assert [x["montant_ht"] for x in r["lignes"]] == ["0.99","0.99","1.00"]


def test_allocation_remise_ligne_et_globale():
    r = preparer_assiettes_tva([
        item("A", q="2", price="30.00", discount="10.00"),
        item("B", q="1", price="50.00", discount="0.00"),
    ], "10.00")
    assert r["total_ht_avant_remise_globale"] == "100.00"
    assert [x["montant_ht"] for x in r["lignes"]] == ["45.00","45.00"]


def test_allocation_remise_totale_ou_total_zero():
    r = preparer_assiettes_tva([item()], "100.00")
    assert r["lignes"][0]["montant_ht"] == "0.00"
    r2 = preparer_assiettes_tva([item(price="0.00")], "0.00")
    assert r2["lignes"][0]["montant_ht"] == "0.00"


def test_assiette_au_centime_plus_grand_reste():
    r = preparer_assiettes_tva([
        item("A", price="0.01"), item("B", price="0.01"),
    ], "0.01")
    assert [x["montant_ht"] for x in r["lignes"]] == ["0.00","0.01"]


@pytest.mark.parametrize("corrupt", [
    [item(q="0")],
    [item(q="1.5")],
    [item(q=1)],
    [item(q="1e2")],
    [item(q="001")],
    [item(price=100.0)],
    [item(price="1.001")],
    [item(discount="100.01")],
    [item(discount="-1")],
    [item(sku="")],
    [item(sku="A"), item(sku="A")],
    [{**item(), "code_tva": "TVA_TAUX_NORMAL"}],
    [],
    [item() for _ in range(501)],
])
def test_allocation_ne_permet_pas_une_assiette_corrompue(corrupt):
    with pytest.raises(ApercuFiscalIndisponible):
        preparer_assiettes_tva(corrupt, "0.00")


@pytest.mark.parametrize("discount", [1.0, "NaN", "-1", "100.01", "1.001", None])
def test_remise_globale_invalide(discount):
    with pytest.raises(ApercuFiscalIndisponible):
        preparer_assiettes_tva([item()], discount)


def test_assiette_preparation_n_est_pas_une_validation_fiscale():
    result = preparer_assiettes_tva([item()], "1.00")
    assert result["statut"] == "PREPARATION_ISOLEE_NON_COMPTABILISEE"
    assert set(result["lignes"][0]) == {"sku_id", "montant_ht"}
    assert "code_tva" not in result["lignes"][0]


class FakeRPC:
    def __init__(self):
        self.args = None

    def rpc(self, name, args):
        assert name == "erp_tax_preview_classified"
        self.args = args
        results = []
        total = Decimal("0")
        tva = Decimal("0")
        for line in args["p_lines"]:
            amount = Decimal(line["montant_ht"])
            tax = (amount * Decimal("0.20")).quantize(Decimal("0.01"))
            total += amount
            tva += tax
            results.append({
                "sku_id": line["sku_id"], "montant_ht": f"{amount:.2f}",
                "montant_tva": f"{tax:.2f}", "code_tva": "TVA_TAUX_NORMAL",
                "taux_tva": "0.20", "source_classification": "SOURCE-FICTIVE",
                "source_taux": "TAUX-FICTIF",
                "date_verification_classification": "2026-01-02",
                "date_verification_taux": "2026-01-02",
            })
        data = {
            "date_facture": args["p_date"], "montant_ht": f"{total:.2f}",
            "montant_tva": f"{tva:.2f}", "montant_ttc": f"{total+tva:.2f}",
            "montant_timbre": "0.00", "lignes": results,
            "statut": "CALCUL_ISOLE_NON_COMPTABILISE",
        }
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=data))


def test_preview_panier_vers_rpc_sans_ecriture():
    db = FakeRPC()
    result = simuler_tva_panier(
        db_client=db,
        panier=[item(), item("SKU-TEST-B", price="50.00")],
        date_facture="2026-11-09", remise_globale="15.00",
    )
    assert db.args["p_lines"] == [
        {"sku_id": "SKU-TEST-A", "montant_ht": "90.00"},
        {"sku_id": "SKU-TEST-B", "montant_ht": "45.00"},
    ]
    assert result["simulation"]["montant_ht"] == "135.00"
    assert result["simulation"]["montant_tva"] == "27.00"
    assert result["statut"] == "PREPARATION_ISOLEE_NON_COMPTABILISEE"


def test_preview_panier_refuse_especes_sans_creer_facture():
    db = FakeRPC()
    with pytest.raises(ApercuFiscalIndisponible, match="Timbre"):
        simuler_tva_panier(db_client=db, panier=[item()],
            date_facture="2026-11-09", paiement_especes=True)
