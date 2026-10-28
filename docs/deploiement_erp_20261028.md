# ERP Mortier — livraison contrôlée du 28/10/2026

## Installation Supabase vérifiée

Projets :
- TEST : `ffuhbmcfyexsbjwhryvj`
- PRODUCTION : `wenydirqtmkywbxbxfal`

| Source de migration | Migration effectivement appliquée | État |
|---|---|---|
| sql/012_reglementation_registre.sql | erp_016_registre_reglementaire_20261028 | TEST et PRODUCTION |
| sql/014_scf_journal.sql | erp_017_scf_journal_private_20261028 | TEST et PRODUCTION |
| sql/015_paie_privee.sql | erp_018_paie_privee_20261028 | TEST et PRODUCTION |
| sql/013_facturation_parametree.sql | **NON APPLIQUÉE** | Conserver le circuit Ventes actuel |

Les numéros 012–015 sont **déjà utilisés par d'autres migrations** dans la base production. Ne jamais déduire l'historique de déploiement du numéro de fichier SQL. La source de vérité est `supabase_migrations.schema_migrations` et les noms ci-dessus.

## Contrôles réalisés en production
- 11 tables présentes et RLS active sur chacune.
- 0 table accessible en SELECT par `anon` ou `authenticated`.
- 11 tables accessibles au service `service_role`.
- Aucune ligne de paramètres légaux ni bulletin ajouté.
- Aucune table métier historique modifiée par ces migrations additives.

## Livraison du code
La branche de livraison contient les calculateurs SCF, IRG, préparation de paie, rapports internes, contrôles d'accès et Guides. Le circuit de création de factures `modules/ventes/service.py` et son écran `modules/ventes/views.py` sont **maintenus identiques à la branche main antérieure**, car la migration SQL 013 couperait la création de factures sans paramètres fiscaux confirmés.

Le fichier `sql/013_facturation_parametree.sql` est livré comme **brouillon NON EXECUTE**. Les composants `core/fiscalite_service.py` et `core/fiscalite_facturation.py` existent mais ne sont pas branchés aux ventes en production.

## Fonctionnalités non encore validées juridiquement
- Classification fiscale des SKU, taux TVA 9 %/19 %, exonérations, avoirs historiques et fait générateur selon livraison / encaissement.
- Timbre espèces : taux, plafond, exceptions, fait générateur et textes officiels datés.
- IRG : exonérations, abattements et arrondis réels ; bulletins officiellement validés.
- CNAS/CASNOS : assiettes, catégories, cotisations, déclarations, échéances.
- G50 et autres états fiscaux officiels.
- Tests SQL transactionnels en situation de concurrence et de clôture : complémentaires aux contrôles de schéma et tests Python.

**L'existence des tables et des calculateurs ne signifie pas la conformité réglementaire ni l'autorisation d'émettre des documents officiels.**

## Protection des données locales
La branche GitHub ne contient pas les changements non commités du poste utilisateur :
`README.md`, `modules/help/views.py`, `scripts/sauvegarder_google_sheets.py`.
Avant `git pull` local, sauvegarder ou isoler ces modifications ; ne jamais écraser ces fichiers.

## Critères de sortie
- CI GitHub complète verte sur la branche de livraison.
- Fusion GitHub `main` uniquement après le contrôle ci-dessus.
- Vérifier la branche réellement déployée par Streamlit avant de déclarer l'application mise à jour.
- Contrôles production post-fusion sur tables, droits et historique des migrations.


## Optimisation 019 — index SCF/paie

Le contrôle Supabase de performance a détecté 3 clés étrangères non indexées
dans les nouvelles tables. Migration additive `sql/019_indexes_scf_paie.sql`
appliquée sur TEST puis PRODUCTION sous le nom
`erp_019_indexes_scf_paie_20261028`.

Quatre index installés : journal des pièces SCF, numéro de compte des lignes
SCF, période des bulletins, et recherche des pièces validées par date.
Aucune écriture métier modifiée. Les autres recommandations de performance
concernent les tables historiques et restent hors de ce déploiement.

La validation transactionnelle SCF sur TEST a été effectuée dans un
`BEGIN/ROLLBACK` : pièce équilibrée validée, mutation des lignes refusée,
clôture d'exercice irréversible, nouvelle pièce refusée en période close.
Après rollback, les compteurs de données de test sont nuls.
