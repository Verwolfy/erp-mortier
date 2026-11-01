# Lot 13 — Preuves de migrations Supabase : état contrôlé, sans rejeu

**Date : 01/11/2026. Statut : audit en lecture seule, pas une certification du schéma.**

## Diagnostic confirmé sur PRODUCTION

- Projet Supabase `wenydirqtmkywbxbxfal` : **23 versions natives** dans `supabase_migrations.schema_migrations` (21 ERP, puis 2 NextGen). Registre `public.schema_migrations` : **0 ligne**. Les registres sont distincts ; ne pas « compléter » l'applicatif à partir de noms.
- Archivage SQL `sql/supabase_applied/` : quatre migrations historiques du 27/10, dont la version `erp_013` représentée par **six segments de revue**. Ces archives sont *déclarées appliquées*, sans comparaison d'empreintes avec le SQL réellement transmis à Supabase.
- Les versions **016–018** possèdent seulement des fichiers proches par thème, explicitement à revoir / tester ; on ne peut pas conclure à une identité SQL.
- Les versions **019–032** possèdent des fichiers candidats à rapprochement par numéro/thème ; la similarité de nom ne prouve ni contenu exact, ni exécution depuis ce fichier.
- Les deux versions natives **NextGen** renvoient à des propositions présentes dans le dépôt privé `nextgen-website/sql/`. Ces fichiers sont marqués **PROPOSITION_NON_EXECUTEE** : ne jamais les identifier comme scripts effectivement exécutés. Aucun lien binaire n'est revendiqué.
- L'audit Supabase « sécurité » remonte **86 informations** de type `rls_enabled_no_policy`. Ce constat ne démontre pas une fuite : RLS sans politique peut correspondre à un refus par défaut. Pour `produits`, `erp_sku_fiscalite`, `site_produits` et `site_demandes`, les droits SELECT directs `anon` et `authenticated` sont absents et RLS est activée. Aucun changement ACL/RLS entrepris.

## Outils non destructifs ajoutés

- `docs/migration_evidence_20261101.json` : **instantané de métadonnées de version et de noms**, avec chemins des archives déclarées, candidats ou propositions. **Ni dump SQL, ni mots de passe, ni migrations à lancer.**
- `scripts/auditer_preuves_migrations.py` : vérifie localement les fichiers de preuve, calcule le SHA-256 de leurs octets et produit un tableau Markdown. Il **n'importe aucun client Supabase**, ne fait pas de requête réseau, n'exécute aucun SQL et ne modifie aucun fichier.
- `tests/test_auditer_preuves_migrations.py` : tests de refus des chemins hors dépôt, des liens symboliques échappant au dépôt, des versions dupliquées, des classifications trompeuses, des candidats manquants et de la distinction du dépôt site optionnel.

Exécuter depuis le dépôt ERP :

```bash
python scripts/auditer_preuves_migrations.py
python -m pytest -q tests/test_auditer_preuves_migrations.py
```

Pour contrôler également les chemins du dépôt privé du site (si un clone **autorisé** est disponible localement) :

```bash
python scripts/auditer_preuves_migrations.py --site-root /chemin/vers/nextgen-website
```

**Le SHA-256 produit caractérise le fichier Git consulté, non le contenu de la migration exécutée**. Une comparaison de preuve exigera, séparément, le texte d'exécution authentifié ou des preuves vérifiables de schéma et une validation par un responsable habilité.

## Décisions de sécurité

- **Ne pas rejouer les DDL/GRANT/RLS** à partir d'un nombre ou d'un nom apparemment concordant.
- **Ne pas remplir `public.schema_migrations`** avec des hash calculés depuis des *candidats*.
- **Ne pas publier** les propositions de scripts Site, les jeux de preuves privées ou le catalogue caché.
- **Ne pas changer** automatiquement les 86 tables signalées par l'advisor : revoir ACL, schéma exposé et chemins de service avant décision.

## Suite

1. Valider la CI du scanner hors ligne (tests et suite ERP intégrale), puis fusionner sur `main`.
2. Rapprocher la source réellement exécutée avec les scripts pour **chaque** version encore non prouvée ; isoler les divergences et soumettre la régularisation au contrôle technique.
3. Vérifier le commit Streamlit réellement déployé via une session autorisée : un build vert ne l'établit pas.
4. Continuer les preuves matières/SKU sans inventer tarifs, fiscalité, densité ou fournisseur.
