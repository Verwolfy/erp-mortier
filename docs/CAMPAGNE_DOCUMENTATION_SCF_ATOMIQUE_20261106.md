# Campagne 041 — Documentation SCF atomique des coûts industriels
Date : 2026-11-06

## Résultat
Déploiement réussi dans `Verwolfy/erp-mortier`, branche `main`, puis sur Supabase TEST (`ffuhbmcfyexsbjwhryvj`) et PROD (`wenydirqtmkywbxbxfal`).

## Problème corrigé
Avant le lot 041, la méthode Python `document_pool` écrivait un lien `erp_cost_pool_scf_evidence` et changeait ensuite `erp_cost_pools.statut` en deux requêtes distinctes. Une rupture réseau entre les requêtes pouvait laisser une preuve partiellement enregistrée. Le même appel ne pouvait pas être rejoué si le pool était déjà `DOCUMENTE`.

## Modifications
- `sql/041_couts_industriels_documentation_atomique.sql` : fonction PostgreSQL `erp_cost_document_pool_atomic(text,text,uuid,bigint,text)` SECURITY DEFINER, réservée à `service_role`. Vérifie une période brouillon et verrouille sa ligne, l'état du pool, la pièce SCF validée, le débit, le plafond et les justificatifs. Insère la preuve et change le statut dans **une seule transaction SQL**. Un appel strictement identique est idempotent ; une preuve différente est refusée.
- `modules/production/cost_service.py` : supprime les deux écritures HTTP et invoque une RPC unique. Après réponse réseau incertaine, le service accepte `SIMULATION` ou `DOCUMENTE` pour permettre le rejeu exact, tout en conservant les contrôles de droits Production + Finance.
- `tests/test_industrial_cost_service_full_suite.py` : mocks de la RPC, vérification du payload, de l'absence de deux écritures directes, du rejeu après réponse inconnue et du refus de confirmation incertaine.
- `tests/test_industrial_cost_scf_evidence_contract.py` : contrat de la fonction SQL et de son invocation.
- `sql/test_isole/20261106_documentation_atomique_ROLLBACK.sql` : création initiale de deux preuves par RPC, vérification des pools `DOCUMENTE`, rejeu identique, refus d'une preuve différente et contrôles d'allocation, le tout dans une transaction ROLLBACK.
- `sql/test_isole/20261105_couts_industriels_referentiel_ROLLBACK.sql` : régression des états précédents et de l'idempotence de la RPC.

## Preuves réelles sur TEST
- Migration 041 : `success=true`.
- `COST_ATOMIC_DOCUMENT_OK` : OF1=70 DZD, OF2=140 DZD, total analytique imputé 210 DZD; ROLLBACK.
- `COST_REFERENCE_OK` : régression existante, ROLLBACK.
- `COST_ACL_OK` : droits de validation, ROLLBACK.
- `COST_ROLE_MATRIX_OK` : refus pour clients `anon` et `authenticated`, ROLLBACK.
- Contrôle indépendant après les essais : 0 période de test, 0 pool et 0 preuve.
- Nouvelle fonction SQL : `anon_exec=false`, `auth_exec=false`, `service_exec=true`.

## CI GitHub
Commit de validation `870f0ed930ea13b36cbb483c73f490e9c75deeea` :
- Tests ERP : **success**, **2 581 passed, 7 skipped, 133 warnings** : https://github.com/Verwolfy/erp-mortier/actions/runs/42204611485
- Audit de réconciliation : **success** : https://github.com/Verwolfy/erp-mortier/actions/runs/42204611373

## Production
Migration `erp_cost_document_pool_atomic_20261106` : `success=true`.
Après déploiement : `periods=0`, `pools=0`, `proofs=0`, RPC accessible au seul `service_role` (pas à `anon` ou `authenticated`).
Aucune écriture SCF, de stock ou de CUMP; aucune donnée fictive transférée à PROD.

## Limites
- Le test **navigateur authentifié réel** reste à exécuter avec deux profils utilisateurs dans une session applicative. Les tests Python et SQL ne simulent pas une vraie session interactive.
- Aucune preuve comptable réellement validée n'était présente dans les contrôles antérieurs de production; le nouveau processus nécessite un document SCF valide et sa ligne au débit.
- L'éligibilité d'une dépense à la formation du coût industriel relève toujours d'une validation Finance : la cohérence du débit SCF ne vaut pas certification métier.
- La transaction couvre la documentation SCF, pas la validation de période, qui demeure un circuit distinct.

## Suite
1. Vérifier le dernier statut du projet Supabase TEST après demande de pause.
2. Valider l'interface Streamlit réelle avec compte Production+Finance et compte lecture limitée, idéalement via ChatGPT Work.
3. Prévoir une revue des permissions `SECURITY DEFINER`, du propriétaire SQL et des données d'audit pour des connexions serveur réelles, sans donner de droit client à la RPC.
