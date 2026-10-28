"""Tests de simulation du timbre de quittance, basés sur art. 46 LF 2025.

La fixture est isolée : elle n'installe aucune valeur fiscale en base.
Elle ne constitue pas une attestation de conformité du processus de vente.
"""
from decimal import Decimal

import pytest

from core.timbre_quittance import TimbreNonDisponible, calculer_timbre_quittance


def regle(**overrides):
    law = {
        "code": "TIMBRE_QUITTANCE_ESPECES_BAREME",
        "type_regle": "calcul",
        "date_effet": "2025-01-01",
        "date_fin": None,
        "date_verification": "2026-10-28",
        "statut_juridique": "en_vigueur",
        "niveau_confiance": "CONFIRMEE",
        "source": "JO Algerien no 84 du 26-12-2024, art. 46 et 47, LF 2025",
        "donnees": {
            "unite_tranche": "100",
            "montant_exonere_jusqua": "300",
            "minimum_perception": "5",
            "dispense_paiement_electronique": True,
            "tarifs": [
                {"jusqua": "30000", "tarif_par_tranche": "1"},
                {"jusqua": "100000", "tarif_par_tranche": "1.5"},
                {"jusqua": None, "tarif_par_tranche": "2"},
            ],
        },
    }
    law.update(overrides)
    return law


def simulate(amount, *, method="ESPECES", rules=None, instant="2026-10-28"):
    return calculer_timbre_quittance(
        amount, instant, method, [regle()] if rules is None else rules,
    )


@pytest.mark.parametrize("amount,expected", [
    ("0", "0.00"),
    ("300", "0.00"),
    ("300.01", "5.00"),
    ("20000", "200.00"),
    ("30000", "300.00"),
    ("30000.01", "451.50"),
    ("100000", "1500.00"),
    ("100000.01", "2002.00"),
    ("150000", "3000.00"),
    ("1000000", "20000.00"),
])
def test_barème_par_montant_total_et_tranches_entieres(amount, expected):
    result = simulate(amount)
    assert result["montant_timbre"] == Decimal(expected)
    assert result["statut"] == "SIMULATION_NON_VALIDEE"


def test_paiement_electronique_exonere_sur_regle_validee():
    result = simulate("150000", method="ELECTRONIQUE")
    assert result["montant_timbre"] == Decimal("0.00")
    assert result["nombre_tranches"] == 0


def test_electronique_non_confirme_refuse():
    rule = regle()
    rule["donnees"]["dispense_paiement_electronique"] = False
    with pytest.raises(TimbreNonDisponible):
        simulate("150000", method="ELECTRONIQUE", rules=[rule])


@pytest.mark.parametrize("methode", ["VIREMENT", "CHEQUE", "CARTE", "", None])
def test_moyens_non_parametres_refuses(methode):
    with pytest.raises(TimbreNonDisponible):
        simulate("20000", method=methode)


@pytest.mark.parametrize("value", [True, 1.5, "-1", "NaN", "Infinity", None])
def test_montant_non_valide_refuse(value):
    with pytest.raises(TimbreNonDisponible):
        simulate(value)


@pytest.mark.parametrize("overrides", [
    {"statut_juridique": "projet"},
    {"niveau_confiance": "A_VERIFIER"},
    {"source": ""},
    {"date_effet": "2027-01-01"},
    {"date_verification": None},
])
def test_absence_de_regle_validee_refusee(overrides):
    with pytest.raises(TimbreNonDisponible):
        simulate("20000", rules=[regle(**overrides)])


def test_doublon_de_regle_refuse():
    with pytest.raises(TimbreNonDisponible):
        simulate("20000", rules=[regle(), regle()])


def test_version_du_barème():
    old = regle(date_fin="2026-06-30")
    new = regle(date_effet="2026-07-01")
    assert simulate("100000.01", rules=[old, new], instant="2026-06-30")["montant_timbre"] == Decimal("2002.00")
    assert simulate("100000.01", rules=[old, new], instant="2026-07-01")["montant_timbre"] == Decimal("2002.00")


def test_audit_piste_juridique():
    result = simulate("20000")
    assert "art. 46" in result["source"]
    assert result["date_verification"] == "2026-10-28"


@pytest.mark.parametrize("field,value", [
    ("unite_tranche", "0"),
    ("unite_tranche", "-1"),
    ("montant_exonere_jusqua", "NaN"),
    ("minimum_perception", "Infinity"),
    ("tarifs", []),
    ("tarifs", [{"jusqua": None, "tarif_par_tranche": "1"},
                {"jusqua": "30000", "tarif_par_tranche": "1.5"}]),
    ("tarifs", [{"jusqua": "30000", "tarif_par_tranche": "1"}]),
    ("tarifs", [{"jusqua": None, "tarif_par_tranche": "-1"}]),
])
def test_configuration_mal_formee_refusee(field, value):
    data = regle()
    data["donnees"][field] = value
    with pytest.raises(TimbreNonDisponible):
        simulate("20000", rules=[data])


def test_type_progressif_refuse_sur_timbre():
    with pytest.raises(TimbreNonDisponible):
        simulate("20000", rules=[regle(type_regle="progressif")])


def test_tarif_au_millieme_refuse():
    r = regle()
    r["donnees"]["tarifs"][0]["tarif_par_tranche"] = "1.001"
    with pytest.raises(TimbreNonDisponible):
        simulate("20000", rules=[r])
