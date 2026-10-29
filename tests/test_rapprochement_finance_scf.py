"""Réconciliation Finance / SCF : tests fictifs isolés, zéro DB."""
from copy import deepcopy
import pytest
from core.rapprochement_finance_scf import (
    AuditTresorerieIndisponible, auditer_reglements_vers_scf,
)


def compte(ident, typ, numero):
    return {"compte_id": ident, "statut": "OUI",
            "type_compte": typ, "numero_compte": numero}


ACCOUNTS = [
    compte("CPT-CAISSE", "Caisse", "530"),
    compte("CPT-BANQUE", "Banque", "512"),
    compte("CPT-CLIENT", "Tiers client", "411"),
    compte("CPT-FOURNISSEUR", "Tiers fournisseur", "401"),
]


def paiement(id="REGF-1", **mod):
    base = {
        "reglement_id": id, "type_flux": "ENCAISSEMENT", "statut": "VALIDE",
        "date_reglement": "2026-10-29", "partenaire_id": "CLI-1",
        "compte_id": "CPT-CAISSE", "montant_total": "150.00",
        "montant_alloue": "50.00",
    }
    base.update(mod)
    return base


def ligne(id, compte_id, debit, credit, source="REGF-1", **mod):
    base = {
        "ecriture_id": id, "date_ecriture": "2026-10-29",
        "document_source_id": source, "compte_id": compte_id,
        "debit": debit, "credit": credit, "lettrage_id": "",
    }
    base.update(mod)
    return base


def ecritures():
    return [
        ligne("E1", "CPT-CAISSE", "150.00", "0"),
        ligne("E2", "CPT-CLIENT", "0", "150.00"),
    ]


def audit(p=None, e=None, c=None):
    return auditer_reglements_vers_scf(
        [paiement()] if p is None else p,
        ecritures() if e is None else e,
        ACCOUNTS if c is None else c,
    )


def test_encaissement_equilibre_non_poste():
    result = audit()
    assert result["reglements_rpc_valides"] == 1
    assert result["montant_encaisse"] == "150.00"
    assert result["montant_decaisse"] == "0.00"
    assert result["ecritures"][0]["total_credit"] == "150.00"
    assert result["ecritures"][0]["total_debit"] == "150.00"
    assert result["ecritures"][0]["statut"] == "VERIFIE_FINANCE_NON_COMPTABILISE_SCF"
    assert {x["numero_compte_saisi"] for x in result["ecritures"][0]["lignes"]} == {"530", "411"}


def test_decaissement_fournisseur():
    p = [paiement(type_flux="DECAISSEMENT", compte_id="CPT-BANQUE",
                  partenaire_id="FOURN-1", montant_total="200", montant_alloue="0")]
    e = [ligne("E1", "CPT-BANQUE", "0", "200"),
         ligne("E2", "CPT-FOURNISSEUR", "200", "0")]
    result = audit(p, e)
    assert result["montant_encaisse"] == "0.00"
    assert result["montant_decaisse"] == "200.00"


def test_plusieurs_encaissements_sans_double_compte():
    p = [paiement(), paiement("REGF-2", montant_total="50", montant_alloue="0")]
    e = ecritures() + [
        ligne("E3", "CPT-CAISSE", "50", "0", source="REGF-2"),
        ligne("E4", "CPT-CLIENT", "0", "50", source="REGF-2"),
    ]
    result = audit(p, e)
    assert result["reglements_rpc_valides"] == 2
    assert result["montant_encaisse"] == "200.00"


def test_historique_non_rpc_est_distinct():
    p = [paiement(), paiement("REG-LEGACY-1")]
    e = ecritures() + [ligne("AUTRE", "CPT-CLIENT", "9", "0", source=None)]
    result = audit(p, e)
    assert result["reglements_rpc_valides"] == 1
    assert result["reglements_historiques_hors_controle"] == 1


def test_absence_de_paiements_ou_ecritures_autorisee():
    result = audit([], [], [])
    assert result["reglements_rpc_valides"] == 0
    assert result["montant_encaisse"] == "0.00"


@pytest.mark.parametrize("p,e,c", [
    ([paiement(), paiement()], ecritures(), ACCOUNTS),
    ([paiement(statut="BROUILLON")], ecritures(), ACCOUNTS),
    ([paiement(type_flux="INCONNU")], ecritures(), ACCOUNTS),
    ([paiement(date_reglement="29/10/2026")], ecritures(), ACCOUNTS),
    ([paiement(montant_total="NaN")], ecritures(), ACCOUNTS),
    ([paiement(montant_total=True)], ecritures(), ACCOUNTS),
    ([paiement(montant_alloue="151")], ecritures(), ACCOUNTS),
    ([paiement()], [], ACCOUNTS),
    ([paiement()], ecritures()[:1], ACCOUNTS),
    ([paiement()], ecritures() + [ecritures()[0]], ACCOUNTS),
    ([paiement()], [ligne("E1", "CPT-CAISSE", "100", "0"), ecritures()[1]], ACCOUNTS),
    ([paiement()], [ligne("E1", "CPT-CAISSE", "150", "0"),
                     ligne("E2", "CPT-CLIENT", "0", "149")], ACCOUNTS),
    ([paiement()], [ligne("E1", "CPT-CAISSE", "0", "150"), ecritures()[1]], ACCOUNTS),
    ([paiement()], [ligne("E1", "CPT-CAISSE", "150", "1"), ecritures()[1]], ACCOUNTS),
    ([paiement()], [ligne("E1", "CPT-CAISSE", "150", "0"),
                     ligne("E2", "CPT-CAISSE", "0", "150")], ACCOUNTS),
    ([paiement()], [ligne("E1", "CPT-CAISSE", "150", "0",
                         date_ecriture="2026-10-28"), ecritures()[1]], ACCOUNTS),
    ([paiement()], [ligne("E1", "CPT-UNKNOWN", "150", "0"), ecritures()[1]], ACCOUNTS),
    ([paiement()], ecritures(), [compte("CPT-CAISSE", "Caisse", "530"),
                                 compte("CPT-CAISSE", "Caisse", "530")] + ACCOUNTS[2:]),
    ([paiement()], ecritures(), [compte("CPT-CAISSE", "Tiers client", "530")] + ACCOUNTS[1:]),
    ([paiement()], [ligne("E1", "CPT-CAISSE", "150", "0", source="REGF-X"),
                     ecritures()[1]], ACCOUNTS),
])
def test_fail_closed_sur_ecritures_incoherentes(p, e, c):
    with pytest.raises(AuditTresorerieIndisponible):
        audit(deepcopy(p), deepcopy(e), deepcopy(c))


def test_entrees_non_structurees_refusees():
    with pytest.raises(AuditTresorerieIndisponible):
        auditer_reglements_vers_scf("not-list", [], [])


def test_sans_ecriture_scf_sql_dans_le_module():
    import inspect
    import core.rapprochement_finance_scf as m
    source = inspect.getsource(m)
    assert "get_supabase_client" not in source
    assert ".insert(" not in source
    assert ".update(" not in source
    assert ".rpc(" not in source
