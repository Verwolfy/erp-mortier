# OPT-03 — Diagnostic de provenance : projection minimale contrôlée

**Date :** 2026-11-08. **Branche :** `perf/dashboard-provenance-projection-20261108`.

## Constat vérifié

Le diagnostic automatique des neuf tableaux de bord parcourt six tables : `factures`, `reglements`, `ordres_fabrication`, `commandes_achats`, `pipeline`, `employes`. Il sert à compter les identifiants commençant par `DEMO` ou `SIM`, mais chargeait toutes leurs colonnes via `charger_donnees`. Cet indicateur ne qualifie **pas** la nature comptable ou juridique des lignes et ne justifie jamais leur suppression.

## Changement

- La lecture stricte `fetch_data_strict(..., only_primary_key=True)` sélectionne uniquement la **clé primaire autorisée** de la table. La même vérification de rôle Supabase est refaite à **chaque page**, et le résultat complet est vérifié par `count='exact'`, ordre déterministe, détection de clés dupliquées, bornes de 10 000 lignes et rejet des réponses incomplètes.
- Dans `dashboard_read_scope` en mode réel, le diagnostic lit seulement les identifiants ; si les données complètes sont déjà en cache de rendu, il les réutilise sans lecture supplémentaire.
- Le cache de provenance est limité à un seul rendu `ContextVar`, jamais inter-utilisateurs ni inter-rendus. Les erreurs réseau et RBAC ne sont pas cachées ; les identifiants métier manquants ou invalides sont refusés puis retirés du cache.
- Le mode DEMO ne lit **aucune donnée Supabase**, et le contrôle historique hors portée reste compatible.
- Aucune modification SQL, aucune migration, aucun GRANT/RLS, aucune écriture, aucune suppression de données DEMO/SIM, aucune modification de formule KPI.

## Mesure et limites

**Avant :** jusqu'à six jeux de lignes complets téléchargés à chaque rendu réel. **Après :** six projections d'une colonne par table, sauf si une des tables a déjà été lue par un KPI. Le nombre de requêtes initiales reste au plus six pour le diagnostic ; le volume transféré doit diminuer, mais **aucun gain en ms ni en octets n'a été mesuré** sur l'ERP hébergé. Le panneau actif peut relire certaines données complètes en plus des identifiants ; les mesures d'usage détermineront si le compromis reste favorable.

## Vérifications

- Tests de lecture : projection réellement égale à la clé, revérification RBAC par page, contrôle de volume, rejet d'une page incomplète, refus d'options invalides.
- Tests Dashboard : six sources, noms et totaux inchangés, cache limité au rendu, provenance invalidée en erreur, absence de requête en DEMO, réutilisation d'une lecture KPI et compatibilité hors contexte.
- Suite pytest GitHub et tests de non-régression Dashboard. Ne fusionner que si le HEAD PR est vert puis revalider le HEAD `main`.

## Suite du projet

1. Mesurer le trafic réseau et les temps de rendu par panneau, sans données privées dans les logs.
2. Mesurer le coût de création d'un client Supabase **sans** réutiliser un contexte Auth inter-sessions.
3. Garder `DB-UNI-01` gelé et réserver les tests d'écriture à une base TEST isolée.
4. Recette authentifiée et rotation rapide du mot de passe administrateur : nécessaires avant homologation de production.
