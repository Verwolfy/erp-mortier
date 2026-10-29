"""Contrôles de qualification SKU en lecture seule (données fictives de test)."""
from copy import deepcopy
import pytest

from core.couverture_tva_sku import (
    QualificationTVAIndisponible, verifier_couverture_tva,
)


def sku(sid="SKU-A"):
    return {"sku_id": sid, "pf_id": "PF-TEST", "actif": "OUI"}


def fiche(**kwargs):
    item = {
        "sku_id": "SKU-A", "date_effet": "2026-01-01",
        "date_fin": None, "categorie_tva": "NORMAL",
        "code_parametre": "TVA_TAUX_NORMAL", "statut": "VALIDEE",
        "source_juridique": "URL_FICTIVE_TEST", "justification": "TEST",
        "date_verification": "2026-01-02",
        "valide_par": "COMPTABLE_TEST", "date_validation": "2026-01-03",
    }
    item.update(kwargs)
    return item


def check(skus=None, fiches=None, date="2026-10-29"):
    return verifier_couverture_tva(
        [sku()] if skus is None else skus,
        [fiche()] if fiches is None else fiches, date
    )


def test_aucun_dossier_ne_produit_pas_de_taux_implicite():
    result = check(skus=[sku("SKU-A"), sku("SKU-B")], fiches=[])
    assert result["nombre_skus"] == 2
    assert result["par_statut"] == {
        "NON_CLASSE": 2, "A_VALIDER": 0, "VALIDE": 0}
    assert result["facturation_automatique_autorisee"] is False
    assert all(x["categorie_tva"] is None for x in result["lignes"])


def test_validee_mais_facturation_non_autorisee():
    result = check()
    assert result["par_statut"]["VALIDE"] == 1
    assert result["lignes"][0]["code_parametre"] == "TVA_TAUX_NORMAL"
    assert result["facturation_automatique_autorisee"] is False


def test_proposition_incomplete_est_a_valider():
    data = fiche(statut="A_VALIDER", categorie_tva=None,
                 code_parametre=None, source_juridique=None)
    r = check(fiches=[data])
    assert r["par_statut"]["A_VALIDER"] == 1
    assert r["lignes"][0]["categorie_tva"] is None


def test_date_future_ne_declenche_pas_de_tva_automatique():
    result = check(fiches=[fiche(date_effet="2027-01-01")])
    assert result["par_statut"]["NON_CLASSE"] == 1


def test_date_fin_passee_declenche_non_classe():
    result = check(fiches=[fiche(date_fin="2026-06-30")])
    assert result["par_statut"]["NON_CLASSE"] == 1


def test_periodes_disjointes_admises():
    a = fiche(date_fin="2026-06-30")
    b = fiche(date_effet="2026-07-01", categorie_tva="NORMAL",
              code_parametre="TVA_TAUX_NORMAL")
    result = check(fiches=[a, b])
    assert result["lignes"][0]["categorie_tva"] == "NORMAL"


@pytest.mark.parametrize("fiches", [
    [fiche(), fiche()],
    [fiche(), fiche(date_effet="2026-06-01")],
    [fiche(code_parametre="TVA_TAUX_REDUIT")],
    [fiche(categorie_tva="EXONERE", code_parametre="TVA_TAUX_NORMAL")],
    [fiche(categorie_tva=None)],
    [fiche(statut="VALIDE", source_juridique="")],
    [fiche(statut="VALIDE", date_validation=None)],
    [fiche(statut="PROJET")],
    [fiche(date_fin="2025-01-01")],
    [fiche(sku_id="SKU-ABSENT")],
])
def test_refus_classification_incoherente(fiches):
    with pytest.raises(QualificationTVAIndisponible):
        check(fiches=fiches)


def test_sku_duplique_refuse():
    with pytest.raises(QualificationTVAIndisponible):
        check(skus=[sku(),sku()])


def test_resultat_vide_explicite():
    result = check(skus=[], fiches=[])
    assert result["nombre_skus"] == 0
    assert result["facturation_automatique_autorisee"] is False


@pytest.mark.parametrize("source", ["abc", None, {"sku_id": "A"}])
def test_liste_de_sku_invalide_refusee(source):
    with pytest.raises(QualificationTVAIndisponible):
        verifier_couverture_tva(source, [], "2026-10-29")


def test_affichage_actifs_seulement_mais_dossiers_inactifs_conserves():
    actifs = sku("SKU-A")
    inactif = {**sku("SKU-B"), "actif": "NON"}
    historique = fiche(sku_id="SKU-B")
    r = verifier_couverture_tva(
        [actifs, inactif], [historique], "2026-10-29", uniquement_actifs=True
    )
    assert r["nombre_skus"] == 1
    assert r["par_statut"] == {
        "NON_CLASSE": 1, "A_VALIDER": 0, "VALIDE": 0
    }
    assert [x["sku_id"] for x in r["lignes"]] == ["SKU-A"]
    assert r["facturation_automatique_autorisee"] is False


def test_sku_inactif_qualifie_absent_du_catalogue_actif():
    actif = sku("SKU-A")
    inactif = {**sku("SKU-B"), "actif": "NON"}
    r = verifier_couverture_tva(
        [actif, inactif], [fiche(sku_id="SKU-B")], "2026-10-29",
        uniquement_actifs=False
    )
    assert r["nombre_skus"] == 2
    assert r["par_statut"]["VALIDE"] == 1


def test_filtre_actifs_ne_cache_pas_dossier_inactif_incoherent():
    actifs = [sku("SKU-A"), {**sku("SKU-B"), "actif": "NON"}]
    with pytest.raises(QualificationTVAIndisponible, match="incohérente"):
        verifier_couverture_tva(
            actifs, [fiche(sku_id="SKU-B", code_parametre="TVA_TAUX_REDUIT")],
            "2026-10-29", uniquement_actifs=True,
        )


def test_filtre_actifs_requires_bool():
    with pytest.raises(QualificationTVAIndisponible, match="Filtre"):
        verifier_couverture_tva([sku()], [], "2026-10-29", uniquement_actifs="oui")


def test_dossier_valide_apres_date_operation_reste_en_attente_asof():
    result = check(
        fiches=[fiche(date_validation="2026-11-02",
                      date_verification="2026-11-01")],
        date="2026-10-29",
    )
    assert result["par_statut"] == {
        "NON_CLASSE": 0, "A_VALIDER": 1, "VALIDE": 0
    }
    assert result["lignes"][0]["categorie_tva"] is None
    assert result["lignes"][0]["code_parametre"] is None
    assert result["lignes"][0]["date_validation"] == "2026-11-02"
    assert result["facturation_automatique_autorisee"] is False


def test_dossier_devenu_valide_apres_validation():
    result = check(
        fiches=[fiche(date_validation="2026-11-02",
                      date_verification="2026-11-01")],
        date="2026-11-02",
    )
    assert result["par_statut"]["VALIDE"] == 1
    assert result["lignes"][0]["categorie_tva"] == "NORMAL"


def test_validation_antérieure_a_verification_refusee():
    with pytest.raises(QualificationTVAIndisponible, match="antérieure"):
        check(fiches=[fiche(date_verification="2026-04-10",
                            date_validation="2026-04-09")])


def test_dossier_non_valide_ne_montre_pas_categorie_proposee():
    result = check(fiches=[fiche(statut="A_VALIDER")])
    assert result["par_statut"]["A_VALIDER"] == 1
    assert result["lignes"][0]["categorie_tva"] is None
    assert result["lignes"][0]["code_parametre"] is None


def test_taux_reduit_est_incompatible_avec_politique_ventes():
    with pytest.raises(QualificationTVAIndisponible, match="incohérente"):
        check(fiches=[
            fiche(categorie_tva="REDUIT", code_parametre="TVA_TAUX_REDUIT")
        ])


def test_exoneration_n_est_pas_une_categorie_sku_autorisee():
    with pytest.raises(QualificationTVAIndisponible, match="incohérente"):
        check(fiches=[
            fiche(categorie_tva="EXONERE", code_parametre=None)
        ])
