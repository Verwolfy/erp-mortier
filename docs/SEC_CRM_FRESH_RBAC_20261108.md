# SEC-CRM — Autorisations fraîches depuis Supabase

Date : 2026-11-08. Branche : `security/sec-crm-fresh-rbac-20261108`.

## Vulnérabilité initiale

Avant ce lot, `modules/crm/views.py` exigeait une session et vérifiait `has_permission()`, mais utilisait **le rôle mémorisé dans `st.session_state.user.role`**. Une révocation du rôle en base après connexion n'interdisait pas nécessairement l'ouverture du CRM ni les formulaires de création en cours de session. La boîte NextGen était mieux protégée : `modules/crm/site_requests.py` relisait déjà le compte serveur indépendamment.

## Correction

- `_crm_access()` relit `users.user_id,role,actif` via Supabase à **chaque rendu**, filtre sur l'identifiant de la session et limite à deux lignes pour détecter une identité ambigüe.
- Refus de toute session non authentifiée, utilisateur manquant, compte inactif, identité incohérente, rôle absent ou permission `CRM.lecture` absente.
- Le droit `CRM.ecriture` dépend exclusivement du rôle **reçu du serveur**, jamais du rôle déclaré en session.
- Au clic `Ajouter au pipeline` et `Enregistrer l'interaction`, un **second** `_crm_access()` refuse les droits expirés, la désactivation, le changement d'utilisateur et le passage en lecture seule **avant** l'appel du service de création.
- En cas de panne réseau, le contrôle est fail-closed et la page affiche un message générique ; seuls les noms des catégories d'erreur (jamais le message ni les données) peuvent être consignés en avertissement technique.
- La lecture paginée et le verrou confidentialité NextGen existants sont inchangés ; ils disposent en outre de leur propre contrôle serveur.
- Aucun SQL, migration, RLS/GRANT, écriture en base, variable de production ou donnée client n'est modifié.

## Tests

- Nouveaux `tests/test_sec_crm_fresh_rbac.py` : plus de vingt scénarios paramétrés, dont identité absente/dupliquée, role session ADMIN vs rôle serveur limité, compte inactif, permission refusée, panne serveur, révocation entre deux rendus et avant écriture, changement d'utilisateur en soumission, succès de création encore autorisé.
- Les fixtures existantes de `tests/test_lot09_crm_lazy.py` simulent un compte serveur confirmé afin de continuer à vérifier l'isolation des quatre panneaux.
- `tests/test_strict_reads_ui.py` isole volontairement son test de rendu des données non disponibles ; l'autorisation serveur est désormais testée séparément et directement.
- Deux suites complètes GitHub Actions doivent être vertes sur la PR, puis deux sur le commit `main` après fusion. Les avertissements `1 warning` des précédentes suites sont à qualifier ultérieurement.

## Périmètre et limites

Ce lot sécurise **le point d'entrée UI CRM et la soumission des deux formulaires**. Il ne constitue pas un audit complet des RPC de mutation sous-jacents ni des politiques de table Supabase : ces services doivent demeurer sous contrôle pour les appels hors UI, avec un environnement TEST isolé avant les essais d'écriture.

La version déployée sur Streamlit Cloud n'a pas été contrôlée dans une session authentifiée. L'environnement Supabase TEST reste inactif. Le mot de passe administrateur communiqué précédemment doit être renouvelé hors du dépôt ; ne jamais copier le secret dans ce document, les tests ou GitHub.

## Suite recommandée

1. Vérifier après déploiement que CRM refuse instantanément un compte désactivé ou un rôle rétrogradé (sur une base TEST autorisée, jamais en modifiant le compte administrateur de production).
2. Examiner les services CRM `insert_hybrid` et `create_interaction` pour maintenir les contraintes RBAC/idempotence aussi lors d'appels non UI.
3. Mesurer les coûts de ces relectures avec OPT-04 ; ne jamais mettre en cache inter-session une autorisation d'écriture.
4. Reprendre les lots de performance et l'environnement TEST en gardant les règles fiscales/SCF gelées jusqu'à validation documentée.
