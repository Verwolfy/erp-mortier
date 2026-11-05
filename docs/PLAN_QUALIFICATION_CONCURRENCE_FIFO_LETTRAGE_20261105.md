# ERP — Plan de qualification restant après concurrence (05/11/2026)

## État prouvé
- Dépôt : `Verwolfy/erp-mortier`, `main`, commit de référence `30fbb2a8`.
- Projet TEST `ffuhbmcfyexsbjwhryvj` confirmé `INACTIVE` via Supabase le 05/11/2026.
- Production `wenydirqtmkywbxbxfal` confirmée `ACTIVE_HEALTHY`; aucune écriture pendant cette reprise.
- Réception concurrente, clôture OF concurrente et FIFO **séquentiel transactionnel** documentés dans `docs/TESTS_CONCURRENCE_RECEPTION_OF_20261105.md`.
- GitHub commit status ne publie aucun statut et l'outil commit workflow runs ne retourne aucun run; ces réponses **ne prouvent pas** que GitHub Actions est vert. Contrôler les workflows de push séparément.

## Lots à exécuter sur TEST uniquement
### 1 — FIFO avec deux sorties simultanées
- Restaurer TEST, attendre `ACTIVE_HEALTHY`, vérifier `SELECT 1`.
- Faire deux lots MP distincts et datés (ancien 4 kg, récent 7 kg).
- Démarrer deux connexions indépendantes avec identifiants d'opération distincts : chacune demande 6 kg. Résultat attendu : une seule opération acceptée; l'autre refusée pour stock restant (5 kg), sans stock négatif.
- Auditer lignes de lot, journal de mouvement, stock total, opérations d'idempotence et éventuels verrous.
- Rejouer la même opération acceptée : aucun doublon. Rejouer avec charge contradictoire : refus.
- Versionner PREP, SESSION_A, SESSION_B, AUDIT, NETTOYAGE avec garde stricte sur projet TEST et identifiants isolés. Vérifier le nettoyeur **avant** toute insertion.

### 2 — Double lettrage
- Créer dans TEST une facture et deux demandes de règlement utilisant deux operation_id distincts mais la même référence bancaire; sessions indépendantes.
- Critères : une seule allocation, aucun dépassement du montant dû, aucun paiement ni journal dupliqué; contrôle de l'idempotence et rejet des données contradictoires.
- Nettoyage ciblé, puis contrôle zéro résidu.

### 3 — API et interface
- Tester RPC avec contexte authentifié réel et RLS/permissions utilisateur final; ne pas assimiler un appel `service_role` à un contrôle RLS.
- Vérifier les neuf écrans Streamlit et les parcours boutons en session autorisée (affichage, erreurs, soumission, rechargement).
- Simuler timeout réseau puis rejeu identique et vérifier l'absence de doubles effets.

## Barrières de publication
1. Pas de simulation sur production.
2. Pas de PREP sans script de nettoyage vérifié.
3. Pas de succès déclaré sans sorties SQL brutes et audit post-nettoyage.
4. Pas de changement de RLS, GRANT, rôles ni règles fiscales sans validation explicite.
5. CI GitHub vérifiée sur le SHA exact et tests Python/SQL réussis avant conclusion.
6. Remettre TEST en pause après campagne.

## Suite immédiate
- Préparer scripts de tests FIFO concurrents et double lettrage à partir des signatures SQL réellement versionnées, exécuter uniquement en TEST, publier les preuves dans `docs/`.
- La validation d'un expert-comptable algérien demeure nécessaire avant toute exploitation réglementaire.
