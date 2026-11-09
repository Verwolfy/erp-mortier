"""TVA par SKU : jeux purement fictifs, sans contact avec Supabase."""
from decimal import Decimal

import pytest

from core.fiscalite_lignes_sku import (
    ClassificationFiscaleIndisponible,
    simuler_tva_par_sku,
)


def cls(sku="SKU-A", categorie="NORMAL", **changes):
    code = {"NORMAL": "TVA_TAUX_NORMAL", "REDUIT": "TVA_TAUX_REDUIT"}.get(categorie)
    row = {
        "sku_id": sku, "date_effet": "2026-01-01", "date_fin": None,
        "categorie_tva": categorie, "code_parametre": code,
        "statut": "VALIDEE", "source_juridique": "SOURCE-FICTIVE-TEST",
        "justification": "Qualification fictive validée seulement par le test",
        "date_verification": "2026-01-02", "date_validation": "2026-01-03",
        "valide_par": "VALIDATEUR-TEST",
    }
    row.update(changes)
    return row


def rate(code="TVA_TAUX_NORMAL", valeur="0.20", **changes):
    row = {
        "code": code, "valeur": valeur, "unite": "fraction",
        "date_effet": "2026-01-01", "date_fin": None,
        "statut_juridique": "en_vigueur", "niveau_confiance": "CONFIRMEE",
        "source": "SOURCE-FICTIVE-TEST", "date_verification": "2026-01-03",
    }
    row.update(changes)
    return row


def simulate(lines=None, classes=None, rates=None, **kw):
    return simuler_tva_par_sku(
        lines if lines is not None else [{"sku_id": "SKU-A", "total_ligne_ht": "100.00"}],
        classes if classes is not None else [cls()],
        rates if rates is not None else [rate()],
        "2026-06-01",
        **kw,
    )


def test_un_seul_sku_valide_avec_trace_et_aucune_ecriture():
    result = simulate()
    assert result["montant_ht"] == Decimal("100.00")
    assert result["montant_tva"] == Decimal("20.00")
    assert result["montant_ttc"] == Decimal("120.00")
    assert result["montant_timbre"] == Decimal("0.00")
    assert result["statut"] == "SIMULATION_SANS_ECRITURE"
    assert result["lignes"][0]["source_classement"] == "SOURCE-FICTIVE-TEST"
    assert result["lignes"][0]["source_taux"] == "SOURCE-FICTIVE-TEST"


def test_taux_mixtes_avec_remise_globale_au_centime():
    result = simulate(
        lines=[
            {"sku_id": "SKU-A", "total_ligne_ht": "100.00"},
            {"sku_id": "SKU-B", "total_ligne_ht": "50.00"},
        ],
        classes=[cls(), cls("SKU-B", "REDUIT")],
        rates=[rate(), rate("TVA_TAUX_REDUIT", "0.05")],
        remise_globale="15.00",
    )
    assert [l["montant_ht"] for l in result["lignes"]] == [
        Decimal("90.00"), Decimal("45.00")
    ]
    assert [l["montant_tva"] for l in result["lignes"]] == [
        Decimal("18.00"), Decimal("2.25")
    ]
    assert result["montant_ht"] == Decimal("135.00")
    assert result["montant_tva"] == Decimal("20.25")
    assert result["montant_ttc"] == Decimal("155.25")


def test_repartition_plus_forts_restes_et_stabilite():
    result = simulate(
        lines=[
            {"sku_id": "SKU-A", "total_ligne_ht": "0.01"},
            {"sku_id": "SKU-A", "total_ligne_ht": "0.01"},
            {"sku_id": "SKU-A", "total_ligne_ht": "0.01"},
        ],
        remise_globale="0.02",
    )
    assert [l["montant_ht"] for l in result["lignes"]] == [
        Decimal("0.00"), Decimal("0.00"), Decimal("0.01")
    ]
    assert result["montant_ht"] == Decimal("0.01")


def test_changement_taux_dans_le_temps_sans_constante():
    old = rate(date_fin="2026-03-31")
    new = rate(date_effet="2026-04-01", valeur="0.22")
    result = simulate(rates=[old, new])
    assert result["montant_tva"] == Decimal("22.00")
    assert result["lignes"][0]["date_effet_taux"] == "2026-04-01"


@pytest.mark.parametrize("classification", [
    cls(statut="A_VALIDER"),
    cls(categorie="EXONERE"),
    cls(categorie="HORS_CHAMP"),
    cls(categorie="NORMAL", code_parametre="TVA_TAUX_REDUIT"),
    cls(source_juridique=""),
    cls(justification=None),
    cls(valide_par=""),
    cls(date_validation=None),
    cls(date_verification="invalid"),
    cls(date_effet="2027-01-01"),
    cls(date_fin="2026-01-01"),
])
def test_classification_non_homologuee_ou_hors_date_refusee(classification):
    with pytest.raises(ClassificationFiscaleIndisponible):
        simulate(classes=[classification])


def test_deux_classifications_actives_meme_statut_valide_sont_bloquees():
    with pytest.raises(ClassificationFiscaleIndisponible, match="2 classification"):
        simulate(classes=[cls(), cls(date_effet="2026-04-01")])


def test_classement_non_valide_actif_parallele_refuse():
    with pytest.raises(ClassificationFiscaleIndisponible, match="non validée"):
        simulate(classes=[cls(), cls(statut="A_VALIDER", date_effet="2026-02-01")])


def test_classifications_historiques_expirees_ou_futures_sont_ignorees():
    result = simulate(classes=[
        cls(statut="A_VALIDER", date_effet="2025-01-01", date_fin="2025-12-31"),
        cls(),
        cls(statut="A_VALIDER", date_effet="2027-01-01"),
    ])
    assert result["montant_tva"] == Decimal("20.00")


def test_absence_dune_classification_refusee():
    with pytest.raises(ClassificationFiscaleIndisponible, match="0 classification"):
        simulate(classes=[])


@pytest.mark.parametrize("params", [
    [],
    [rate(niveau_confiance="RECOUPEE")],
    [rate(), rate(date_effet="2026-05-01", valeur="0.30")],
    [rate(), rate(date_effet="2026-05-01", statut_juridique="a_confirmer")],
    [rate(valeur="1.01")],
    [rate(valeur="NaN")],
    [rate(unite="pct")],
])
def test_regle_non_confirmee_ambigue_ou_absente_refusee(params):
    with pytest.raises(ClassificationFiscaleIndisponible):
        simulate(rates=params)


@pytest.mark.parametrize("montant", [
    0.1, True, None, "NaN", "Infinity", "-1.00",
    "0.001", "1000000000000000", [],
])
def test_assiette_refuse_valeur_non_exacte_ou_invalide(montant):
    with pytest.raises(ClassificationFiscaleIndisponible):
        simulate(lines=[{"sku_id": "SKU-A", "total_ligne_ht": montant}])


@pytest.mark.parametrize("discount", ["0.001", "101.00", -1, True, 0.1])
def test_remise_incorrecte_refusee(discount):
    with pytest.raises(ClassificationFiscaleIndisponible):
        simulate(remise_globale=discount)


@pytest.mark.parametrize("cash", [True, "false", None, 1])
def test_especes_ou_type_ambigu_refuse(cash):
    with pytest.raises(ClassificationFiscaleIndisponible, match="Timbre"):
        simulate(paiement_especes=cash)


def test_remise_decent_pourcent_interdite():
    with pytest.raises(ClassificationFiscaleIndisponible):
        simulate(remise_globale="100.01")


def test_assiette_nulle_sans_remise():
    result = simulate(lines=[{"sku_id": "SKU-A", "total_ligne_ht": "0.00"}])
    assert result["montant_ttc"] == Decimal("0.00")


def test_montant_ttc_trop_grand_est_refuse():
    with pytest.raises(ClassificationFiscaleIndisponible, match="Total facture"):
        simulate(lines=[{"sku_id": "SKU-A", "total_ligne_ht": "999999999999999.99"}])


def test_taille_de_lot_bloquee():
    with pytest.raises(ClassificationFiscaleIndisponible):
        simulate(lines=[])
    with pytest.raises(ClassificationFiscaleIndisponible):
        simulate(lines=[{"sku_id": "SKU-A", "total_ligne_ht": "0.01"}] * 501)
