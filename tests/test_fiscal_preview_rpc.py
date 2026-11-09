"""Scénarios fictifs TAX-V2 : aucun réseau ni écriture Supabase."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from modules.ventes.fiscal_preview import ApercuFiscalIndisponible, simuler_tva_sql

DATE = "2026-11-09"
INPUT = [{"sku_id": "SKU-FICTIF-N", "montant_ht": "100.00"}]


def payload():
    return {
        "date_facture": DATE,
        "montant_ht": "100.00",
        "montant_tva": "20.00",
        "montant_timbre": "0.00",
        "montant_ttc": "120.00",
        "statut": "CALCUL_ISOLE_NON_COMPTABILISE",
        "lignes": [{
            "sku_id": "SKU-FICTIF-N",
            "montant_ht": "100.00",
            "montant_tva": "20.00",
            "code_tva": "TVA_TAUX_NORMAL",
            "taux_tva": "0.20",
            "source_classification": "QUALIFICATION-FICTIVE",
            "source_taux": "TAUX-FICTIF",
            "date_verification_classification": "2026-01-02",
            "date_verification_taux": "2026-01-03",
        }],
    }


def client(data=None):
    mock = Mock()
    mock.rpc.return_value.execute.return_value = SimpleNamespace(
        data=payload() if data is None else data
    )
    return mock


def test_preview_lecture_seule_sans_classes_client():
    db = client()
    got = simuler_tva_sql(db_client=db, lignes=deepcopy(INPUT), date_facture=DATE)
    assert got["montant_tva"] == "20.00"
    db.rpc.assert_called_once_with("erp_tax_preview_classified", {
        "p_lines": [{"sku_id": "SKU-FICTIF-N", "montant_ht": "100.00"}],
        "p_date": DATE, "p_cash": False,
    })
    db.rpc.return_value.execute.assert_called_once_with()
    assert "insert" not in db.method_calls
    assert "update" not in db.method_calls


@pytest.mark.parametrize("corrupted", [
    [{"sku_id": "SKU-FICTIF-N", "montant_ht": "100.00",
      "code_tva": "TVA_TAUX_REDUIT"}],
    [{"sku_id": "SKU-FICTIF-N", "montant_ht": 100.0}],
    [{"sku_id": "SKU-FICTIF-N", "montant_ht": "100.001"}],
    [{"sku_id": "", "montant_ht": "100.00"}],
    [{"sku_id": "SKU-FICTIF-N", "montant_ht": "NaN"}],
    [{"sku_id": "SKU-FICTIF-N", "montant_ht": "-10.00"}],
    INPUT * 2,
    [],
    [{"sku_id": "SKU-FICTIF-N", "montant_ht": "1e2"}],
])
def test_preview_rejette_donnees_non_qualifiees_avant_rpc(corrupted):
    db = client()
    with pytest.raises(ApercuFiscalIndisponible):
        simuler_tva_sql(db_client=db, lignes=corrupted, date_facture=DATE)
    db.rpc.assert_not_called()


@pytest.mark.parametrize("date", [None, "2026-02-30", "20261109", "2026-1-9"])
def test_preview_rejette_date_invalide_avant_rpc(date):
    db = client()
    with pytest.raises(ApercuFiscalIndisponible):
        simuler_tva_sql(db_client=db, lignes=INPUT, date_facture=date)
    db.rpc.assert_not_called()


@pytest.mark.parametrize("cash", [True, None, 0, "false"])
def test_preview_rejette_especes_ou_type_invalide(cash):
    db = client()
    with pytest.raises(ApercuFiscalIndisponible):
        simuler_tva_sql(db_client=db, lignes=INPUT, date_facture=DATE,
                        paiement_especes=cash)
    db.rpc.assert_not_called()


@pytest.mark.parametrize("field,value", [
    ("statut", "COMPTABILISE"),
    ("date_facture", "2026-11-08"),
    ("montant_ht", "101.00"),
    ("montant_tva", "21.00"),
    ("montant_timbre", "1.00"),
    ("montant_ttc", "121.00"),
])
def test_preview_rejette_en_tete_sql_corrompu(field, value):
    response = payload()
    response[field] = value
    with pytest.raises(ApercuFiscalIndisponible):
        simuler_tva_sql(db_client=client(response), lignes=INPUT, date_facture=DATE)


@pytest.mark.parametrize("field,value", [
    ("sku_id", "SKU-FICTIF-AUTRE"),
    ("montant_ht", "99.00"),
    ("montant_tva", "20.01"),
    ("code_tva", "TVA_EXONERE"),
    ("taux_tva", "0.21"),
    ("source_classification", ""),
    ("source_taux", None),
    ("date_verification_taux", "2026-02-30"),
    ("date_verification_classification", None),
])
def test_preview_rejette_ligne_sql_corrompue(field, value):
    response = payload()
    response["lignes"][0][field] = value
    with pytest.raises(ApercuFiscalIndisponible):
        simuler_tva_sql(db_client=client(response), lignes=INPUT, date_facture=DATE)


@pytest.mark.parametrize("data", [None, [], {"statut": "ERREUR"}, {"lignes": []}])
def test_preview_rejette_reponse_incomplete(data):
    db = client()
    db.rpc.return_value.execute.return_value = SimpleNamespace(data=data)
    with pytest.raises(ApercuFiscalIndisponible):
        simuler_tva_sql(db_client=db, lignes=INPUT, date_facture=DATE)


def test_preview_error_rpc_refuse_sans_second_appel():
    db = client()
    db.rpc.side_effect = TimeoutError("Réponse perdue")
    with pytest.raises(ApercuFiscalIndisponible, match="aucune facture créée"):
        simuler_tva_sql(db_client=db, lignes=INPUT, date_facture=DATE)
    db.rpc.assert_called_once()


def test_preview_refuse_client_absent():
    with pytest.raises(ApercuFiscalIndisponible, match="Client serveur"):
        simuler_tva_sql(db_client=None, lignes=INPUT, date_facture=DATE)
