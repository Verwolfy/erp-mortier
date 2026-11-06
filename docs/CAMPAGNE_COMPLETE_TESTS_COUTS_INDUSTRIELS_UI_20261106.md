# Campagne exhaustive automatisée — Coûts industriels, SCF et interface Production
Date : 6 novembre 2026.

## Résultats vérifiés
- Dépôt : `Verwolfy/erp-mortier`, branche `main`.
- Suite complète GitHub Actions au commit `09d62c572ea51279eb2a2fcb1fd07c47d1ea7590` : **2 576 tests réussis, 7 ignorés, 0 échec, 133 warnings**.
- Workflow tests ERP : https://github.com/Verwolfy/erp-mortier/actions/runs/42200520088 — **success**.
- Workflow audit de réconciliation : https://github.com/Verwolfy/erp-mortier/actions/runs/42200520100 — **success**.
- Un échec intermédiaire a été identifié : un test d’assiette attendait un texte différent du champ effectivement simulé. Attente corrigée, nouvelle CI entièrement verte.

## Tests ajoutés
1. `tests/test_industrial_cost_views_flows.py` : 16 cas d’interface Streamlit **avec doublures**, couvrant lecture seule, refus si droit Finance absent, indisponibilité backend, période validée, aucune période, absence de natures, consentement de validation, validation réussie/refusée, liaison UUID/ligne SCF, erreur documentaire, création de période, création de charge, assiette par OF, création de nature.
2. `tests/test_industrial_cost_service_full_suite.py` : tests paramétrés des droits Production+Finance, refus d’accès sans habilitation, UUID invalides, identifiants SCF invalides, motifs insuffisants, pièces non validées, ligne introuvable, débit nul/non numérique/insuffisant, succès du lien documentaire, période figée, OF non terminé, OF hors période, clé inconnue et montants invalides.
3. `sql/test_isole/20261106_couts_industriels_matrice_roles_ROLLBACK.sql` : contrôles du vrai rôle SQL `anon`, `authenticated` et `service_role` sur Supabase TEST, sans persistance.
4. Régressions historiques déjà versionnées dans `sql/test_isole/20261105_couts_industriels_referentiel_ROLLBACK.sql`, `..._acl_ROLLBACK.sql` et `..._authentifie_refus_ROLLBACK.sql`.

## SQL réellement exécuté sur TEST
Projet `ffuhbmcfyexsbjwhryvj`, restauré à `ACTIVE_HEALTHY` avant exécution :
- `COST_ROLE_MATRIX_OK` : `anon` et `authenticated` ne lisent pas les preuves / le rapprochement et n’exécutent pas la RPC de validation ; `service_role` ne peut pas UPDATE directement les périodes.
- `COST_REFERENCE_OK` : imputation OF1 70 DZD, OF2 140 DZD, total 210 DZD, vérification des pièces SCF validées, plafond des montants, unicité des lignes comptables, blocage après validation.
- `COST_ACL_OK` : tests de validation et verrouillage.
- `AUTHENTICATED_DENIED_OK` : refus de lecture et de RPC pour rôle authentifié.
- Toutes les campagnes sous `BEGIN...ROLLBACK`.
- Contrôle indépendant après tests : **0 résidu** de périodes, pools, drivers, preuves, documents SCF et comptes SCF fictifs.

## Correctifs appliqués au code principal
- `modules/production/cost_service.py` : ajout `can_manage_costs()`, lecture effective des deux droits d’écriture côté serveur.
- `modules/production/cost_views.py` : suppression de l’accès aux formulaires d’écriture si Finance ne l’autorise pas, même lorsque Production passe `can_write=True`. Correction de l’erreur sur les natures de charges vides.
- Aucun changement de schéma supplémentaire, aucune écriture de données en production ni modification des fonctions CUMP/SCF.

## Limites explicites
Les 16 scénarios Streamlit utilisent des **doublures du service et des widgets** ; ce ne sont pas des parcours navigateur avec vraies sessions, véritables cookies ou mots de passe. La campagne SQL teste les rôles PostgreSQL réellement, pas le processus interactif de connexion à l’application. **Test navigateur authentifié réel non réalisé** dans cette campagne ; aucun outil navigateur connecté n’était disponible. Ne pas prétendre le contraire.
Les 7 tests ignorés et les 133 warnings sont ceux de l’ensemble ERP ; leur criticité n’a pas été passée en revue individuellement.
`service_role` reste une clé privilégiée côté serveur : les droits métier sont vérifiés en Python puis par les fonctions SQL.
La conformité de l’éligibilité industrielle des montants au débit SCF reste un contrôle financier humain.

## Suite recommandée
1. Tester sur une instance Streamlit réelle avec un compte Production+Finance et un compte limité, sans communiquer les identifiants dans la conversation ; exécuter le parcours depuis Work/Computer Use si disponible.
2. Valider la revue humaine des montants réellement affectables à la fabrication et les pièces SCF.
3. Confirmer la fin de la suspension Supabase TEST après les derniers essais et laisser le projet arrêté en dehors des campagnes.
