"""Regression Achats 004 : contrats prix, quantites et controles sans acces BDD.

Ces tests ne remplacent PAS l'essai SQL PostgreSQL avec ROLLBACK.
"""
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from modules.achats import service as achats_service
from modules.achats import views as achats_views


def _commande(monkeypatch, **overrides):
    monkeypatch.setattr(achats_service, "get_commandes", lambda: pd.DataFrame())
    captures = []

    def fake_rpc(name, payload, *, receipt):
        captures.append((name, payload, receipt))
        return {"commande_achat_id": "CMA-TEST", "operation_id": payload["p_operation_id"]}

    monkeypatch.setattr(achats_service, "_rpc", fake_rpc)
    data = {
        "fournisseur_id": "FR-TEST", "type_achat": "Matière Première",
        "devise": "EUR", "taux_change": 150,
        "mode_paiement": "Virement", "delai_paiement": "Comptant",
        "date_voulue": "2026-11-02", "panier": [{
            "mp_id": "MP-TEST", "unite_cond": "KG",
            "qte_cond": 10, "qte_totale": 10,
            "prix_unitaire": 2, "total_devise": 20,
        }],
        "operation_id": "ACH-004-TEST",
    }
    data.update(overrides)
    return data, captures


def test_commande_eur_transmet_prix_devise_et_taux_sans_conversion_python(monkeypatch):
    data, calls = _commande(monkeypatch)
    assert achats_service.create_commande_achat(**data) == "CMA-TEST"
    name, payload, receipt = calls[0]
    assert name == "erp_create_purchase_order" and not receipt
    assert payload["p_taux_change"] == "150"
    assert payload["p_lines"][0]["prix_unitaire"] == "2"
    assert payload["p_lines"][0]["total_devise"] == "20"
    assert payload["p_operation_id"] == "ACH-004-TEST"


def test_commande_dzd_interdit_conversion(monkeypatch):
    data, calls = _commande(monkeypatch, devise="DZD", taux_change=2)
    with pytest.raises(ValueError, match="DZD"):
        achats_service.create_commande_achat(**data)
    assert calls == []


def test_commande_refuse_total_incoherent(monkeypatch):
    data, calls = _commande(monkeypatch)
    data["panier"][0]["total_devise"] = 12
    with pytest.raises(ValueError, match="Total de ligne"):
        achats_service.create_commande_achat(**data)
    assert calls == []


def test_commande_refuse_conversion_conditionnement_non_configuree(monkeypatch):
    data, calls = _commande(monkeypatch)
    data["panier"][0]["qte_cond"] = 1
    with pytest.raises(ValueError, match="conditionnement"):
        achats_service.create_commande_achat(**data)
    assert calls == []


def test_commandes_multiples_lignes_meme_mp_prix_moyen(monkeypatch):
    lignes = pd.DataFrame([
        {"mp_id": "MP-TEST", "qte_totale": 10, "prix_unitaire": 2},
        {"mp_id": "MP-TEST", "qte_totale": 5, "prix_unitaire": 4},
    ])
    receptions = pd.DataFrame([{"bon_reception_id": "BR1", "commande_achat_id": "CMA1"}])
    monkeypatch.setattr(achats_views, "get_lignes_bons_reception", lambda _br: pd.DataFrame([
        {"mp_id": "MP-TEST", "quantite_recue": 4},
    ]))
    solde = achats_views._remaining_quantities("CMA1", lignes, receptions)
    assert len(solde) == 1
    assert solde[0]["remaining"] == 11
    assert abs(solde[0]["prix_unitaire"] - 40 / 15) < 1e-12


def test_sql_004_calcul_cout_stock_depuis_commande_et_non_reception():
    sql = (Path(__file__).resolve().parents[1] / "sql" / "004_atomic_purchases.sql").read_text(encoding="utf-8")
    assert "ALTER TABLE public.erp_purchase_operations ENABLE ROW LEVEL SECURITY" in sql
    assert "ALTER TABLE public.erp_purchase_outbox ENABLE ROW LEVEL SECURITY" in sql
    assert "(v_order_price_total/v_ordered) * v_order.taux_change" in sql
    assert "'MP','ENTREE',v_line.mp_id,v_line.qty,v_price" in sql
    assert "'MP','ENTREE',v_line.mp_id,v_line.qty,v_line.price" not in sql
    assert "v_line.qte_cond IS DISTINCT FROM v_line.qte_totale" in sql
