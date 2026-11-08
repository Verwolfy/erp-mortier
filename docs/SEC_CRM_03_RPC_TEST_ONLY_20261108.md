# SEC-CRM-03 — Préparation de la RPC idempotente CRM (TEST UNIQUEMENT)

**État au 8 novembre 2026 :** CANDIDAT NON DÉPLOYÉ. **Ne pas appliquer à la production.**

Dépôt : `Verwolfy/erp-mortier`; branche : `design/sec-crm03-idempotent-rpc-test-only-20261108`.

## Résultat et preuve de schéma

Inspection **en lecture seule** de Supabase PROD `wenydirqtmkywbxbxfal` :
- `public.pipeline` : PK `opportunite_id text`; les colonnes `prospect_nom`, `contact`, `statut`, `commercial_id`, `valeur_estimee numeric`, `probabilite_pct numeric`, `date_creation text`, `date_derniere_action text`.
- `public.interactions` : PK `interaction_id text`, avec `client_id`, `date_creation`, `type_action`, `notes`, `date_rappel`, `statut_rappel` en `text`.
- `public.users` : `user_id`, `role`, `actif` ; `public.permissions` : `role`, `module`, `lecture`, `ecriture`. `public.clients` contient bien `client_id`, `actif`.
- Aucune colonne `operation_id` dans `pipeline` ou `interactions` ; aucun mécanisme transactionnel CRM idempotent vérifié dans la base.
- Supabase TEST `ffuhbmcfyexsbjwhryvj` est actuellement **INACTIVE** : aucune migration, insertion ni test de concurrence réel réalisé.

## Livrables

1. `sql/supabase_pending/erp_035_crm_idempotence_CANDIDAT_NON_EXECUTE.sql` : **brouillon exécutable seulement après revue**, hors du répertoire des migrations appliquées. Contient une table privée `erp_crm_private.operation_receipts`, un identifiant d'opération UUID unique, une RPC `public.erp_crm_create_idempotent` et ses `REVOKE/GRANT`.
2. `modules/crm/idempotency_contract.py` : préparateur pur de requêtes `p_operation_id`, `p_actor_id`, `p_kind`, `p_payload` et validation stricte de la réponse `operation_id`, `document_id`, `kind`, `replayed`. **NON UTILISÉ PAR LE CODE DE PRODUCTION**.
3. `tests/test_sec_crm03_rpc_candidate.py` : scénarios offline de validation, confirmation et invariants statiques SQL.
4. Ce document de conception et de réception.

Le flux de production actuel reste `modules/crm/service.py → insert_hybrid` avec les sécurités de session de SEC-CRM-02 (#70). Aucune nouvelle RPC n'est appelée.

## Contrat transactionnel recherché

- L'application serveur génère **une seule fois** l'UUID `operation_id` et en conserve la valeur **durablement avant le premier envoi** (le dossier Streamlit actuel n'est pas un stockage durable).
- La RPC vérifie toujours le compte, l'état actif et le droit CRM **en base**, également lors d'un rejeu. Le rôle fourni par la session n'est pas une preuve ; `p_actor_id` provient uniquement du backend Streamlit de confiance.
- Sur une nouvelle opération autorisée : vérifier les champs, enregistrer une pièce privée (`operation_id, actor_id, kind, request_payload, document_id`) et **insérer le document métier dans la même transaction PostgreSQL**.
- Sur le même `operation_id` : conflit de clé unique, attente de la transaction concurrente puis verrou `FOR UPDATE`. Si l'auteur, le type ou le JSONB canonique diffère : **refus** ; sinon renvoyer le **même document** et `replayed=true`, sans nouvelle insertion.
- Si l'insertion échoue : rollback PostgreSQL de la pièce privée **et** de la pièce métier. Pas d'état « confirmed » sans document existant.
- Révocation du rôle avant tout rejeu : accès refusé, même si le document existait.
- Retours strictement non sensibles : `operation_id`, `kind`, `document_id`, `replayed`. Aucune note ou donnée client dans la réponse.

### Limites de sécurité importantes

- La RPC candidate est `SECURITY DEFINER` avec `search_path = ''`, mais peut lire/écrire des tables au-delà de la RLS. Elle ne doit être exécutable **que par le rôle serveur `service_role`**, jamais par `anon` ni `authenticated` ni `PUBLIC`. Les `REVOKE` explicites sont indispensables ; les fonctions PostgreSQL peuvent être exécutables par défaut par `PUBLIC`. Suivre les recommandations Supabase [Database Functions](https://supabase.com/docs/guides/database/functions).
- `p_actor_id` est transmis par le backend privilégié ; il **ne constitue pas à lui seul une preuve cryptographique de l'identité**. Ne jamais exposer la clé `service_role` au navigateur ; maintenir une vérification fraîche d'authentification dans Streamlit et l'audit serveur. Une éventuelle adoption de JWT signés doit être conçue séparément.
- Le registre privé mémorise le **JSONB complet**, éventuellement des notes CRM : soumettre sa rétention, ses accès de lecture et sa politique de purge à une revue de confidentialité. Aucun accès `anon/authenticated` n'est prévu.
- Les nouveaux identifiants `OPP-` et `INT-` sont des UUID sous forme hexadécimale ; `OPP-0001` séquentiel est encore généré par le code existant. **Cette évolution du format documentaire requiert validation métier** avant activation et n'est pas rétroactive.
- Les contrôles SQL sur l'état du compte et la matrice `permissions` doivent être éprouvés avec révocation concurrente et plusieurs rôles ; ne pas présumer d'une garantie de révocation instantanée avant tests transactionnels.

## Plan de recette exclusivement sur Supabase TEST

**Préconditions bloquantes :**
- Projet TEST actif, indépendant de la production, et coût vérifié/approuvé si réactivation payante.
- Configurer des **identités factices et clients factices** dans TEST uniquement ; aucune copie de mots de passe ou notes privées de PROD.
- Contrôler le schéma réel, l'absence de fonction homonyme, la propriété/owner de la fonction et du registre, et les privilèges de défaut dans TEST avant application.
- Déployer le SQL candidat sous transaction dans TEST, observer les advisors sécurité et auditer explicitement `has_function_privilege` pour `anon/authenticated/service_role`.
- Vérifier la compatibilité de `gen_random_uuid`, du type UUID et des dates avec PostgreSQL 17.

**Scénarios obligatoires :**
1. Opportunité créée avec un UUID ; résultat `replayed=false`, exactement une pièce et une entrée de registre.
2. Rejeu avec même UUID, acteur, type et contenu : `replayed=true`, **même identifiant**, aucune nouvelle pièce.
3. Interaction idem, avec un client actif de TEST ; notes et rappel cohérents.
4. Rejeu avec contenu différent, type différent ou acteur différent : refus ; aucune seconde pièce ni altération du premier résultat.
5. Deux appels réellement concurrents avec le même UUID : un seul commit ; le perdant reçoit le document du gagnant.
6. Un échec simulé **après l'INSERT métier mais avant COMMIT** : rollback de toutes les lignes et réutilisation contrôlée de l'UUID.
7. Coupure réseau simulée **après COMMIT** : nouvel appel même UUID → réponse confirmée sans duplicata.
8. Compte désactivé ou rôle retiré avant un replay → refus, aucun accès à une pièce étrangère.
9. `anon` et `authenticated` refusés à l'exécution de la fonction, à l'accès au registre et aux notes.
10. Paramètres invalides, références client absentes, JSON inattendu, nombres hors bornes, date invalide : rejet avant mutation.
11. Vérifier le comportement réel de Google Sheets : l'ancien `insert_hybrid` synchronisait vers Sheets ; **ne pas activer la RPC tant qu'un outbox ou un protocole de synchronisation non ambigu n'est pas défini**.
12. Réconciliation après panne depuis **une autre session** et persistance durable des UUID sans fuite de données.

**Après réussite seulement :** proposer une PR d'activation du service Python et de l'UI, avec feature flag FAIL-CLOSED + tests E2E. Valider le niveau de risque avant migration PROD. Ne jamais présumer que la réussite de tests statiques prouve le SQL.

## Prochains risques à traiter

- Le niveau de garantie de la double écriture Sheets/Supabase diffère de la future RPC, et exige une stratégie outbox.
- Autoriser les nouvelles fonctions seulement au backend ; revue de la clé serveur et des politiques RLS effectives.
- Identifier comment assurer une référence de reprise **durable** entre sessions ; le verrou actuel `st.session_state` n'est pas suffisant.
- Déploiement Streamlit Cloud authentifié non vérifié ; rotation du mot de passe administrateur toujours prioritaire.
- Le registre légal et fiscal reste gelé ; ne pas inventer les valeurs SCF/TVA.
