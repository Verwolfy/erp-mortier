"""Règlements et lettrages fictifs : aucun réseau, aucune écriture SQL."""
from decimal import Decimal

import pytest

from core.quittances_rapprochement import (
    RapprochementIndisponible,
    rapprocher_reglements_clients,
    simuler_timbre_sur_encaissement,
)
from tests.test_timbre_quittance import regle


def payment(ident="REG-A", **kw):
    d = {
        "reglement_id": ident, "date_reglement": "2026-10-28",
        "type_flux": "ENCAISSEMENT", "partenaire_id": "CLIENT-1",
        "mode_paiement": "ESPECES", "montant_total": "100.00",
        "montant_alloue": "50.00", "statut": "VALIDE",
    }
    d.update(kw)
    return d


def invoice(ident="FAC-1", **kw):
    d = {
        "facture_id": ident, "client_id": "CLIENT-1",
        "statut": "VALIDE", "type_facture": "FactureClient",
        "montant_ttc": "100.00", "montant_paye": "50.00",
    }
    d.update(kw)
    return d


def letter(ident="LET-1", **kw):
    d = {
        "lettrage_id": ident, "reglement_id": "REG-A",
        "document_id": "FAC-1", "type_document": "FactureClient",
        "montant_applique": "50.00",
    }
    d.update(kw)
    return d


def run(p=None, l=None, f=None):
    return rapprocher_reglements_clients(
        [payment()] if p is None else p,
        [letter()] if l is None else l,
        [invoice()] if f is None else f,
    )


def test_partiel_et_solde_non_affecte():
    x = run()
    assert x["nombre_reglements"] == 1
    assert x["montant_encaisse_total"] == "100.00"
    assert x["reglements"][0]["reste_a_affecter"] == "50.00"
    assert x["reglements"][0]["montant_alloue"] == "50.00"
    assert x["reglements"][0]["factures"] == [
        {"facture_id": "FAC-1", "montant_applique": "50.00"}
    ]
    assert x["reglements"][0]["statut"] == "ETAT_INTERNE_NON_QUITTANCE"


def test_deux_encaissements_sur_la_meme_facture():
    payments = [
        payment("REG-A", montant_total="35", montant_alloue="35"),
        payment("REG-B", montant_total="65", montant_alloue="65"),
    ]
    letters = [
        letter("LET-1", montant_applique="35"),
        letter("LET-2", reglement_id="REG-B", montant_applique="65"),
    ]
    x = run(payments, letters, [invoice(montant_paye="100")])
    assert x["nombre_reglements"] == 2
    assert x["montant_encaisse_total"] == "100.00"
    assert all(p["reste_a_affecter"] == "0.00" for p in x["reglements"])


def test_un_encaissement_sur_deux_factures_sans_double_timbre():
    p = [payment(montant_total="110.00", montant_alloue="110.00")]
    letters = [
        letter(montant_applique="50.00"),
        letter("LET-2", document_id="FAC-2", montant_applique="60"),
    ]
    invoices = [invoice(montant_paye="50"), invoice("FAC-2", montant_ttc="60", montant_paye="60")]
    x = run(p, letters, invoices)
    assert len(x["reglements"]) == 1
    assert len(x["reglements"][0]["factures"]) == 2
    assert len(x["reglements"][0]["factures"]) != x["nombre_reglements"] + 1
    # La simulation utilise le total encaissé (110), pas les lettrages (50 et 60).
    simulation = simuler_timbre_sur_encaissement(p[0], [regle()])
    assert simulation["montant_regle"] == Decimal("110.00")
    assert simulation["statut"] == "SIMULATION_NON_VALIDEE"


def test_reglement_sans_facture_autorise():
    x = run([payment(montant_alloue="0")], [], [])
    assert x["reglements"][0]["reste_a_affecter"] == "100.00"
    assert x["reglements"][0]["factures"] == []


def test_fournisseur_ignore_si_pas_de_confusion():
    p = [
        payment(),
        payment("SUP-1", type_flux="DECAISSEMENT", partenaire_id="SUP", montant_alloue="15"),
    ]
    letters = [
        letter(),
        letter("LET-S", reglement_id="SUP-1", document_id="SUP-F",
               type_document="FactureFournisseur", montant_applique="15"),
    ]
    x = run(p, letters, [invoice()])
    assert x["nombre_reglements"] == 1


def test_reglement_annule_sans_lettrage_exclu():
    x = run([payment(statut="ANNULE")], [], [])
    assert x["nombre_reglements"] == 0


def test_aucun_document_ne_cree():
    assert run([], [], []) == {
        "reglements": [], "nombre_reglements": 0,
        "montant_encaisse_total": "0.00",
        "statut": "RAPPROCHEMENT_INTERNE_NON_CERTIFIE",
    }


@pytest.mark.parametrize("p,l,f", [
    ([payment(), payment()], [letter()], [invoice()]),
    ([payment(montant_alloue="75")], [letter()], [invoice()]),
    ([payment(montant_alloue="110")], [letter()], [invoice()]),
    ([payment(montant_total="10")], [letter()], [invoice()]),
    ([payment(montant_total="NaN")], [letter()], [invoice()]),
    ([payment(montant_total=True)], [letter()], [invoice()]),
    ([payment(montant_total="1.001")], [letter()], [invoice()]),
    ([payment()], [letter(), letter()], [invoice()]),
    ([payment()], [letter(document_id="FAC-X")], [invoice()]),
    ([payment()], [letter(montant_applique="51")], [invoice(montant_paye="50")]),
    ([payment()], [letter()], [invoice(montant_paye="49")]),
    ([payment()], [letter()], [invoice(client_id="CLIENT-X")]),
    ([payment()], [letter()], [invoice(statut="BROUILLON")]),
    ([payment()], [letter()], [invoice(montant_ttc="1")]),
    ([payment()], [letter(type_document="FactureFournisseur")], [invoice()]),
    ([payment(statut="ANNULE")], [letter()], [invoice()]),
    ([payment()], [letter(reglement_id="REG-X")], [invoice()]),
    ([payment()], [letter(type_document="FactureAvoir")], [invoice()]),
])
def test_incoherences_bloquantes(p, l, f):
    with pytest.raises(RapprochementIndisponible):
        run(p, l, f)


def test_timbre_refuse_par_defaut_sans_regle():
    with pytest.raises(RapprochementIndisponible):
        simuler_timbre_sur_encaissement(payment(), [])


@pytest.mark.parametrize("bad", [
    payment(type_flux="DECAISSEMENT"),
    payment(statut="ANNULE"),
    payment(mode_paiement="VIREMENT"),
    payment(mode_paiement="CHEQUE"),
    payment(montant_total="0"),
])
def test_refus_timbre_pas_encaissement_eligible(bad):
    with pytest.raises(RapprochementIndisponible):
        simuler_timbre_sur_encaissement(bad, [regle()])


def test_un_reglement_cash_timbre_sur_montant_encaisse():
    x = simuler_timbre_sur_encaissement(payment(montant_total="150000"), [regle()])
    assert x["montant_timbre"] == Decimal("3000.00")
    assert x["montant_regle"] == Decimal("150000")


def test_paiement_electronique_selon_regle():
    x = simuler_timbre_sur_encaissement(
        payment(mode_paiement="ELECTRONIQUE", montant_total="150000"), [regle()]
    )
    assert x["montant_timbre"] == Decimal("0.00")
