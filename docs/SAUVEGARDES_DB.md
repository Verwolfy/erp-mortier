# Sauvegarde PostgreSQL TEST + PRODUCTION — procédure sans Docker

**Statut : script préparé. Pas de sauvegarde effectivement réalisée ni restaurée par ChatGPT.**

Le fichier `scripts/sauvegarder_supabase_pg.ps1` lance `pg_dump -Fc` pour TEST et PRODUCTION,
conserve les archives **hors du dépôt**, vérifie leur table des matières avec
`pg_restore --list` et calcule les empreintes SHA-256.

## Configuration requise sur Windows

Utiliser PostgreSQL 17 (les exécutables `pg_dump.exe` et `pg_restore.exe` sont déjà
disponibles localement selon les vérifications antérieures). Préparer un fichier
`.pg_service.conf` et un fichier `.pgpass` **hors GitHub**, avec deux services libpq :
`erp_mortier_test` et `erp_mortier_prod`. Conserver ces fichiers secrets dans un
emplacement restreint à ton utilisateur et ne jamais les envoyer dans le chat.

Exemple PowerShell, en adaptant uniquement les chemins (aucun mot de passe en commande) :

```powershell
Set-Location "C:\LH\Perso\ERP_PYT\erp-mortier"
$env:PGSERVICEFILE = "C:\LH\Perso\ERP_PYT\secrets_postgresql\.pg_service.conf"
$env:PGPASSFILE = "C:\LH\Perso\ERP_PYT\secrets_postgresql\.pgpass"
.\scripts\sauvegarder_supabase_pg.ps1 -PostgresBin "C:\LH\Perso\ERP_PYT\outils_postgresql\bin"
```

Sans la configuration libpq privée, le script **doit échouer** ; il ne crée aucune
connexion ni archive fictive. Les dumps contiennent potentiellement des données
personnelles : chiffrement du volume, contrôle des accès et conservation adaptée
sont impératifs.

## Validation avant migration sensible

1. Vérifier que deux archives datées sont présentes et que chaque empreinte
   SHA-256 du manifeste correspond au fichier.
2. Restaurer **une copie isolée**, jamais sur TEST ou PRODUCTION existant,
   avec `pg_restore`, puis comparer structure, comptes et fonctions.
3. Confirmer les stratégies de sauvegarde Supabase et les objets globaux
   PostgreSQL (rôles et privilèges d'instance), non inclus dans un simple
   `pg_dump` de base.
4. Archiver le rapport de restauration et les sauvegardes hors du dépôt.

Le succès de `pg_restore --list` **ne prouve pas** une restauration complète.
Tant qu'une restauration réelle n'est pas vérifiée, le point d'arrêt de
sauvegarde demeure ouvert.
