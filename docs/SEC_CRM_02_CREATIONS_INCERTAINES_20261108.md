# SEC-CRM-02 — Créations incertaines : aucun doublon par réémission automatique

Date : 2026-11-08. Branche : `security/sec-crm-uncertain-insert-20261108`. Dépôt : `Verwolfy/erp-mortier`.

## Constat

Le code CRM précédent utilisait `insert_hybrid("pipeline", data)` ou `insert_hybrid("interactions", data)`. Ce service vérifie bien le compte et les droits, mais une coupure réseau peut survenir **après** l'insertion PostgreSQL : `insert_hybrid` lève alors une exception « non confirmée ». Le rechargement de la page puis une seconde soumission du même formulaire généreraient **un autre identifiant** et pourraient dupliquer une opportunité ou une interaction.

L'ERP ne possède pas encore, pour ces deux tables, de RPC transactionnelle `operation_id` idempotente comparable aux transactions Achats / Ventes. Ne jamais déduire qu'une exception prouve un rollback.

## Correction sans écriture de migration

- Le service CRM enveloppe uniquement les exceptions émises par `insert_hybrid` dans `CRMCreationUncertain(document_id)`, conservant **l'identifiant exact tenté** (`opportunite_id` / `interaction_id`). Les succès et les signatures historiques des fonctions restent inchangés.
- `_crm_create_once` crée un dossier de session `crm_creation_{type}_{user_id}` **avant** d'appeler le service. Il ne fait qu'un appel ; toute exception, timeout ou réponse vide conserve l'état `uncertain`. Seule une référence non sensible est affichée, jamais le payload, la réponse SQL ou une exception brute.
- Tant que le dossier est `uncertain`, aucun formulaire de nouvelle création de même type pour le même utilisateur n'est accessible. Le compte et les permissions CRM sont toujours revalidés via SEC-CRM #69. **Aucune option UI pour forcer le retry ou effacer une tentative incertaine.**
- Si l'insertion retourne une référence valide, l'état devient `confirmed` ; un clic volontaire « Préparer une nouvelle création CRM » permet une nouvelle création après cette confirmation.
- Les deux catégories CRM ont des dossiers séparés par compte utilisateur ; aucun cache partagé, aucune publication de données sensibles, aucune modification du mode NextGen en lecture seule.
- Les doublons déjà présents dans la base ne sont ni masqués ni supprimés.

## Validation

`tests/test_sec_crm_uncertain_insert.py` teste sans réseau les deux chemins de création, la conservation de l'ID exact après erreur, l'absence de retry, la nécessité d'une confirmation explicite, la lecture seule des vues CRM, les erreurs brutes jamais affichées et l'isolation des clés par utilisateur/opération.

Les tests de sécurité SEC-CRM (#69), les essais de navigation et les deux suites complètes GitHub doivent rester verts. Valider aussi le commit fusionné sur `main`.

## Garantie réelle et limites

**Ce n'est pas une idempotence transactionnelle de base.** Cela bloque les réémissions depuis la **même session Streamlit** tant que le dossier y reste. La déconnexion, le redémarrage, plusieurs navigateurs ou un appel direct au service peuvent contourner ce verrou de session. Une insertion simultanée avec un nouvel identifiant reste possible.

Pour rendre les créations CRM strictement idempotentes sur toutes les sessions, il faudrait :
1. Créer une RPC PostgreSQL `creer_opportunite_crm(operation_id, payload)` et une RPC équivalente pour les interactions, validant côté serveur l'identité, les droits et les champs, avec unicité sur l'ID d'opération.
2. Renvoyer le même document sur tout `operation_id` déjà accepté, **seulement si le payload est identique**, et refuser toute divergence.
3. Prévoir un statut d'opération consultable en lecture autorisée après un timeout ; éviter le double-commit et les inserts partiels.
4. Tester rollback, concurrent calls, droits révoqués et reprise réseau **sur une base TEST réellement isolée** puis soumettre le changement transactionnel à une validation technique/critique avant une migration production.

La base TEST Supabase est inactive ; aucun test d'écriture en production ni migration dans ce lot. Le mot de passe administrateur doit être renouvelé indépendamment, sans l'introduire dans GitHub.

## Procédure opérateur en cas d'état incertain

- **Ne jamais cliquer une seconde fois** ni ouvrir une autre session pour reproduire la création.
- Relever uniquement la référence documentaire affichée, puis vérifier manuellement dans Supabase (avec un compte administrateur habilité) la présence, l'identité et le contenu de l'enregistrement.
- Si l'état ne peut être établi avec certitude, **laisser bloqué** et escalader la réconciliation. Le dossier de session n'est pas un journal durable.
- Ne jamais remettre à zéro le dossier incertain par simple rafraîchissement pour « réessayer » ; documenter la résolution et décider du redémarrage contrôlé en environnement autorisé.

## Reprise du projet

Après validation CI, fusionner uniquement si le SHA de PR est vert et revalider `main`. Mesurer le comportement authentifié et l'exécution effective du correctif Streamlit Cloud. En parallèle, avancer sur l'environnement TEST indépendant, les tests E2E, l'audit RLS et la rotation du mot de passe administrateur. Ne jamais inventer des données fiscales ou comptables réglementaires.
