# ERP Mortier — ETAT D'AVANCEMENT (28 octobre 2026)

## Phase en cours
**Phase 0 et réconciliation — audit complémentaire, sans migration.**
Ce fichier reprend les contrôles factuels. Ne pas annoncer la réconciliation terminée.

## GitHub
- Branche principale observée : `main` à `ec98ad5792c981e80b3956fa7cd0a2de905d03a7`.
- Inventaire : 10 branches distantes, 0 PR ouverte avant la branche d'audit.
- `correctif-db-service`, `preparation-sync-bdd-20261027` et sept autres branches historiques : aucun contenu manquant de `main` dans les fichiers comparés ; `feat/reglementation-lot-c-socle-20261028` possède un commit divergent, mais le fichier SQL 012 a le même blob SHA sur les deux branches.
- **Non vérifié** : états du poste Windows, `git status`, `git stash list`, commits locaux non poussés, tags et branche de déploiement Streamlit.
- Les changements locaux historiques connus (`README.md`, `modules/help/views.py`, `scripts/sauvegarder_google_sheets.py`) doivent être préservés ; ne pas appliquer un `git reset` ni une fusion locale non revue.

## Supabase
- TEST `ffuhbmcfyexsbjwhryvj`, PRODUCTION `wenydirqtmkywbxbxfal`.
- Les 2 projets contiennent 81 relations public (tables/vues), 549 colonnes, 178 contraintes, 95 index, 23 fonctions, 6 triggers, 4 politiques, 5 extensions. Empreintes de ces catégories identiques, sauf les permissions des relations.
- **66 différences de droits ACL** entre TEST et PRODUCTION. Ne pas uniformiser sans une décision explicite sur chaque famille de permissions.
- La table `public.schema_migrations` contient **0 ligne** dans chaque projet. Historique interne Supabase : 4 migrations sur TEST et 8 sur PRODUCTION, dont les quatre migrations historiques absentes de l'historique TEST.
- Comptages : 7 clients, 1 facture, 0 employé sur chaque projet ; impossible d'affirmer qu'il n'y a aucune donnée réelle.
- Les migrations additives 016 à 019 ont déjà été enregistrées dans les deux bases ; ne pas les rejouer à l'aveugle.
- Les paramètres réglementaires et règles sont toujours à 0 ; aucune activation de calcul fiscal n'est possible sans valeur juridiquement validée.

## Audit du code
- Les taux fiscaux sont encore codés dans `modules/ventes/service.py` et l'historique `sql/005_atomic_sales.sql` : `TAUX_TVA`, `TAUX_TIMBRE`, `MAX_TIMBRE`, calculs littéraux.
- `sql/013_facturation_parametree.sql` est une **proposition non appliquée** ; l'activer sans données validées bloquerait la facturation.
- Nouveau contrôle : `scripts/auditer_parametres_reglementaires.py` et tests de détection. `--strict` retourne un code d'échec sur les écarts. Scanner volontairement incomplet (à élargir au référentiel total), jamais une certification fiscale.

## Points d'arrêt (non levés)
1. Copie PostgreSQL complète **restaurable** datée sur TEST et PRODUCTION non prouvée. Aucun outil connecté de `pg_dump` disponible.
2. Changement de RLS/GRANT/permissions non autorisé au cas par cas, avec 66 écarts. Ne pas répliquer automatiquement les permissions PRODUCTION plus larges vers TEST.
3. Chargement de taux, seuils, barèmes, échéances non autorisé avant vérification primaire et validation.
4. Synchronisation locale Git, revue de tous les secrets de l'historique, rejouabilité complète sur une base vierge, tests de bout en bout sur `main`/PRODUCTION non démontrés.
5. L'ensemble des lots C-H, y compris les déclarations fiscales officielles et le Guide & Aide complet, reste partiellement développé.

## Décision et prochaine action
**CONTINUER** les tests, diagnostics, guides et corrections de code sans écriture métier risquée.
**ARRÊT POUR VALIDATION** avant toute migration supplémentaire en base, toute homogénéisation des droits, et toute activation des calculs réglementaires.

La validation par un expert-comptable algérien est nécessaire avant toute production réglementaire.
