# NextGen — Lot 5 : onglet CRM non nominatif (préparation)

Date : 2026-11-01.

## Réalisation
- Quatrième onglet « Demandes NextGen » dans l'écran CRM Streamlit existant.
- **Désactivé par défaut** ; le texte de préparation reste visible uniquement pour les utilisateurs disposant d'un accès au module CRM.
- Condition serveur stricte : \`[nextgen] crm_inbox_read_enabled = true\` dans \`st.secrets\`. **Ne pas activer avant validation du traitement des données et de l'usage de la clé serveur.**
- Double contrôle à l'exécution : session authentifiée, lecture fraîche du rôle/compte actif en BDD, permission \`CRM / lecture\` via \`has_permission\`.
- Requête PostgREST \`SELECT demande_id,type_demande,statut,cree_le\` seulement, ordonnée par date, maximum 101 lignes récupérées pour en afficher 100 et détecter une suite.
- Aucun nom d'entreprise, téléphone, e-mail, message ou adresse du demandeur n'est chargé.
- Aucune création de prospect, client, opportunité, interaction ou mise à jour de statut.
- En cas d'erreur, refus et message neutre, sans information personnelle dans les traces.
- Pas de migration SQL, de nouveaux privilèges, de configuration de secrets ni de déploiement Web.
- **Note** : l'activation du drapeau reste une opération de gouvernance ultérieure, indépendante de ce lot.

## Tests
- \`tests/test_nextgen_crm_inbox.py\` : blocage par défaut, utilisateur/role invalides, droits, allowlist, limite de 100, refus PII, absence d'écriture, présence de l'onglet.
- CI de PR dans \`.github/workflows/nextgen_crm_readonly.yml\`.
- Avant intégration à \`main\`, contrôler la CI et la revue des droits ; \`main\` peut être lié au déploiement Streamlit PROD.

## Points restant ouverts
1. Base légale, notice et durée de conservation des demandes personnelles : non validées.
2. Audit de la gestion de la clé \`service_role\` et restriction des privilèges d'écriture préalablement à une éventuelle consultation nominative.
3. Consultation détaillée et qualification humaine : V2, non implémentée.
4. Activer le drapeau serveur uniquement avec la validation adaptée ; ne jamais exposer les secrets à Astro ou aux journaux.

## Lot 6 — Verrou additionnel (2026-11-01)

Le drapeau d'activation exige maintenant **deux booléens serveur strictement vrais** : `nextgen.crm_inbox_read_enabled = true` ET `nextgen.privacy_review_approved = true`. Les chaînes `'true'` ne sont pas acceptées. Aucun de ces drapeaux n'a été activé en production. La revue de confidentialité n'est pas encore approuvée ; la clé `privacy_review_approved` ne doit PAS être configurée tant que cette revue n'a pas été signée. Ce contrôle applicatif n'équivaut pas à une conformité légale.
