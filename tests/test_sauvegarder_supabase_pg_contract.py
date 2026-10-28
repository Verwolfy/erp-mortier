"""Garde-fous statiques du script de sauvegarde — sans connexion DB."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "scripts" / "sauvegarder_supabase_pg.ps1").read_text(encoding="utf-8")
DOC = (ROOT / "docs" / "SAUVEGARDES_DB.md").read_text(encoding="utf-8")


def test_sauvegarde_comprend_production_et_test():
    assert '"PRODUCTION"' in SCRIPT
    assert '"TEST"' in SCRIPT
    assert 'erp_mortier_prod' in SCRIPT
    assert 'erp_mortier_test' in SCRIPT


def test_sauvegarde_hors_git_sans_mot_de_passe_en_argument():
    assert 'Join-Path (Split-Path $repo -Parent) "sauvegardes_erp"' in SCRIPT
    assert 'Destination interdite' in SCRIPT
    assert '--dbname=service=$service' in SCRIPT
    assert '--password=' not in SCRIPT
    assert 'PGPASSWORD=' not in SCRIPT


def test_integrite_archive_et_erreurs():
    for marker in ('--format=custom', '--list', 'Get-FileHash',
                   'SHA256', '$LASTEXITCODE', '.INCOMPLET'):
        assert marker in SCRIPT


def test_documentation_distingue_liste_et_restauration():
    assert 'ne prouve pas' in DOC
    assert 'Restaurer' in DOC
    assert 'hors du dépôt' in DOC
