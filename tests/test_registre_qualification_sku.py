"""Tests d'un registre de qualification SKU sans taux fiscal implicite."""
import pytest

from core.registre_qualification_sku import registre_qualification_sku


def sku(sku_id="SKU-X", fmt="Sac 25kg"):
    return {"sku_id": sku_id, "pf_id": "PF-X", "format": fmt, "unite_vente": "SAC"}


def test_registre_sans_attribution_fiscale():
    rendu = registre_qualification_sku([sku("SKU-B"), sku("SKU-A")])
    assert rendu.index("SKU-A") < rendu.index("SKU-B")
    assert "0/2 classifications" in rendu
    assert rendu.count("| À qualifier | — | — | — | — |") == 2
    assert "0.19" not in rendu and "0.09" not in rendu
    assert "Document de travail non homologué" in rendu


def test_tableau_markdown_echappe_les_separateurs():
    rendu = registre_qualification_sku([sku(fmt="Sac | 25kg")])
    assert r"Sac \| 25kg" in rendu


def test_catalogue_vide_n_est_pas_presenté_comme_valide():
    rendu = registre_qualification_sku([])
    assert "0/0 classifications" in rendu
    assert "Ne pas importer" in rendu


@pytest.mark.parametrize("rows", [
    None, {}, [None], [sku("SKU-A"), sku("SKU-A")],
    [{"sku_id": "SKU-X", "pf_id": "PF-X", "format": "", "unite_vente": "SAC"}],
    [{"sku_id": "SKU-X\nCSV", "pf_id": "PF-X", "format": "Sac", "unite_vente": "SAC"}],
])
def test_donnees_invalides_refusees(rows):
    with pytest.raises(ValueError):
        registre_qualification_sku(rows)


def test_cli_genere_registre_hors_ligne(tmp_path):
    import json
    from scripts.generer_registre_qualification_sku import main

    entree = tmp_path / "sku.json"
    sortie = tmp_path / "registre.md"
    entree.write_text(json.dumps([sku("SKU-T")]), encoding="utf-8")
    assert main(["--entree", str(entree), "--sortie", str(sortie)]) == 0
    registre = sortie.read_text(encoding="utf-8")
    assert "SKU-T" in registre
    assert "À qualifier" in registre
    assert "0/1 classifications" in registre
