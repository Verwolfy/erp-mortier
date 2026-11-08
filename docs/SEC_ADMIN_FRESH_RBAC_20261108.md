# SEC-ADMIN — Rôle et compte actifs confirmés avant Administration

**Date :** 8 novembre 2026. **Branche :** `security/sec-admin-fresh-rbac-20261108`.

## Risque constaté

La page `show_admin_page` utilisait le rôle `st.session_state.user.role` pour décider de l'accès en lecture ou en écriture. Lorsqu'une session déjà ouverte conservait le rôle ADMIN alors que le compte était désactivé ou rétrogradé dans Supabase, l'interface pouvait encore afficher les référentiels avant que les services ne refusent les écritures.

## Correction

- Nouvelle fonction `_admin_access()` : vérifie que la session est authentifiée et porte un identifiant utilisateur non vide, relit `users.user_id,role,actif` dans Supabase, détecte les lignes manquantes/ambiguës, refuse les comptes désactivés, puis vérifie `Administration.lecture` et `Administration.ecriture` contre le rôle **renvoyé par Supabase**.
- Toute erreur réseau, réponse non conforme ou permission révoquée refuse l'accès **avant le premier sélecteur, catalogue ou formulaire**.
- Une habilitation de lecture seule conserve la consultation autorisée mais n'ouvre pas les formulaires de création.
- Les contrôles de service avant écriture restent inchangés ; le module `Sécurité & Utilisateurs` conserve son contrôle spécifique `is_security_manager()`, différent de `Administration.ecriture`.
- Les erreurs internes sont résumées par leur type dans les logs, sans affichage du contenu ni des secrets.

## Tests

- `tests/test_sec_admin_fresh_rbac.py` : cas positifs, sessions invalides, mauvais identifiant, comptes inactifs, rôle rétrogradé, droit lecture révoqué, panne backend et nouvelle vérification à chaque rendu.
- `tests/test_lot14_admin_lazy.py` continue de vérifier la navigation exclusive des dix panels ; son test de performance utilise volontairement un `_admin_access` simulé (les droits frais sont prouvés dans la suite de sécurité indépendante).
- Requiert deux workflows CI complets sur la PR, puis deux workflows sur `main` après fusion.

## Limites

- L'autorisation serveur relit les permissions via `has_permission`. Une lecture authentifiée en direct sur Streamlit Cloud et des tests d'écriture en base TEST isolée restent nécessaires.
- Le client Supabase utilisé par le serveur doit conserver ses secrets côté serveur et ne pas exposer de clé service-role au navigateur.
- Aucune permission, aucun rôle, aucune session réelle, aucune valeur juridique, fiscale ou comptable n'est créée ou modifiée.
- `DB-UNI-01` unique NIF/RC reste gelé.

## Prochain objectif

Après les trois lots, vérifier les deux workflows du dernier `main`, réaliser l'inventaire des onglets encore exécutés à tort, puis stopper les optimisations sans preuve d'amélioration mesurée. Priorités restantes hors du code : base TEST active et isolée, tests E2E authentifiés, rotation des identifiants administrateur, RPC CRM idempotente non déployée et métriques OPT-04.