"""Cas de tests 2026 tirés d'une fiche DGI, non homologués comme bulletins."""
from decimal import Decimal
import pytest

from core.irg_salaires import IRGNonDisponible, simuler_irg_mensuel


def bar(**kwargs):
    # Données illustratives issues des formules publiées par la DGI.
    # date_effet et statut ci-dessous sont UNIQUEMENT des fixtures de tests.
    rule=dict(
        code="IRG_SALAIRES_MENSUEL", type_regle="progressif",
        date_effet="2026-01-01", date_fin=None, date_verification="2026-10-28",
        statut_juridique="en_vigueur",niveau_confiance="CONFIRMEE",
        source="https://www.mfdgi.gov.dz/fr/particuliers/irg-traitements-et-salaires",
        donnees={
            "periode_an":12,"exoneration":"30000","abattement_pct":"0.40",
            "abattement_min":"1000","abattement_max":"1500",
            "tranches":[
                {"jusqua":"240000","taux":"0"},
                {"jusqua":"480000","taux":"0.23"},
                {"jusqua":"960000","taux":"0.27"},
                {"jusqua":"1920000","taux":"0.30"},
                {"jusqua":"3840000","taux":"0.33"},
                {"jusqua":None,"taux":"0.35"},
            ],
            "abattements_supplementaires":{
                "SALARIE":{
                    "seuil":"35000","multiplicateur_num":"137",
                    "multiplicateur_den":"51","deduction_num":"27925",
                    "deduction_den":"8",
                },
                "HANDICAPE_RETRAITE":{
                    "seuil":"42500","multiplicateur_num":"93",
                    "multiplicateur_den":"61","deduction_num":"81213",
                    "deduction_den":"41",
                },
            },
        },
    )
    rule.update(kwargs)
    return rule


def run(base,categorie="SALARIE",rules=None,date="2026-10-28"):
    return simuler_irg_mensuel(
        base,date,categorie,[bar()] if rules is None else rules,
    )


def test_exonere_jusqu_a_30000():
    for salaire in ("0","10000","29999.99","30000"):
        assert run(salaire)["irg_simule"]=="0.00"


def test_mensualisation_50k_abattement_cap():
    x=run("50000")
    assert x["impot_brut"]=="7300.00"
    assert x["premier_abattement"]=="1500.00"
    assert x["irg_simule"]=="5800.00"
    assert x["statut"]=="SIMULATION_NON_VALIDEE"


def test_second_abattement_salarie():
    x=run("33000")
    assert x["premier_abattement"]=="1196.00" or Decimal(x["premier_abattement"]) >= 1000
    assert Decimal(x["irg_simule"]) < Decimal(x["apres_premier_abattement"])


def test_second_abattement_handicape():
    x=run("40000","HANDICAPE_RETRAITE")
    y=run("40000","SALARIE")
    assert Decimal(x["irg_simule"]) <= Decimal(y["irg_simule"])


def test_choix_version():
    r1=bar(date_fin="2026-06-30")
    r2=bar(date_effet="2026-07-01")
    assert run("50000",rules=[r1,r2],date="2026-06-30")["irg_simule"]=="5800.00"
    assert run("50000",rules=[r1,r2],date="2026-07-01")["irg_simule"]=="5800.00"


@pytest.mark.parametrize("bad",[
    {"statut_juridique":"projet"},
    {"niveau_confiance":"DIVERGENTE"},
    {"date_effet":"2027-01-01"},
    {"source":""},
    {"date_verification":None},
    {"type_regle":"echeance"},
    {"donnees":{}},
])
def test_regle_non_valide(bad):
    with pytest.raises(IRGNonDisponible):
        run("50000",rules=[bar(**bad)])


@pytest.mark.parametrize("input",["NaN","Infinity","-1",True,1.5,None])
def test_assiette_invalide(input):
    with pytest.raises(IRGNonDisponible):
        run(input)


def test_conflit_et_absence():
    for rules in ([bar(),bar()],[]):
        with pytest.raises(IRGNonDisponible):
            run("50000",rules=rules)


def test_profil_inconnu():
    with pytest.raises(IRGNonDisponible):
        run("50000",categorie="OCCASIONNEL")


def test_taux_non_confirme_bloque():
    r=bar()
    r["donnees"]["tranches"][2]["taux"]="1.2"
    with pytest.raises(IRGNonDisponible):
        run("50000",rules=[r])


def test_fiche_source_et_date():
    x=run("50000")
    assert "mfdgi.gov.dz" in x["source"]
    assert x["date_verification"]=="2026-10-28"
