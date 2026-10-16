# Installation de la proposition dans le dépôt Verwolfy/erp-mortier

Ce ZIP contient des fichiers **à AJOUTER** à la racine du dépôt (il ne remplace aucun fichier existant). L'ERP actuel n'exploitera ces fichiers qu'après développement d'adaptateurs métiers; **ne pas appliquer la migration à la base de production**.

```bash
# Dans une copie locale de erp-mortier :
unzip erp_mortier_patch.zip -d .
python -m pip install 'pytest>=8,<10'
PYTHONPATH=erp_hardening python -m pytest -q erp_hardening/tests
```

Le fichier `.github/workflows/erp-hardened-tests.yml` lance les tests sur chaque PR modifiant ce module. Appliquer la migration PostgreSQL uniquement sur un environnement isolé et suivre la checklist `erp_hardening/SQL_VALIDATION_CHECKLIST.md`.

**Blocage :** dépôt original non téléchargé dans cette session, aucun push/PR réalisé; la solution est isolée pour réduire les effets de bord sur les modules existants.
