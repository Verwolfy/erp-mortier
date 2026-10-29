# Règle métier TVA — ventes Sofiane ERP

## Périmètre confirmé par l'exploitant (29 octobre 2026)

Pour **ce business et ses ventes clients**, seuls deux traitements sont possibles :

- **Taux normal : 19 %**, obtenu depuis le paramètre daté `TVA_TAUX_NORMAL` de Supabase, sous réserve de sa validation. L'algorithme ne substitue pas de valeur numérique codée en dur.
- **TVA facturée à 0 %** lorsque le **client dispose d'une attestation d'exonération validée**, applicable à la date d'opération et couvrant les SKU concernés. Le mécanisme doit rester identifié comme **exonération client**, et non comme une propriété du SKU ou un taux réduit.
- **Pas de taux réduit à 9 % dans le périmètre Ventes de ce business**. Le paramètre historique `TVA_TAUX_REDUIT`, qui existe encore dans le référentiel commun de production, n'est ni effacé ni utilisable dans le nouveau pont de simulation Ventes.

Il s'agit d'une **règle métier fournie par l'exploitant**, pas d'une affirmation selon laquelle le taux réduit n'existe pas en droit national pour d'autres activités.

## Prérequis de l'exonération client (modèle conservateur à homologuer)

Le module pur `core/exoneration_tva_client.py` exige :
- identité du client `client_id` correspondant exactement au client facturé ;
- `statut='VALIDEE'` et `reference_attestation` non vide ;
- `autorite_emettrice`, `justification`, `valide_par` renseignés ;
- `date_effet`, `date_fin`, `date_verification`, `date_validation` cohérentes et applicables à la date de facture ;
- `sku_ids_couverts` explicite, non vide, sans doublons.

Ce schéma est un **précontrôle interne prudent**, non une preuve que ces seuls champs satisfont toutes les conditions fiscales et administratives en vigueur. Certaines attestations peuvent avoir des plafonds, quantités, destinations ou conditions particulières qui ne sont pas encore modélisés. Ne pas activer la facturation réelle avant examen documentaire et validation des autres restrictions.

## Interfaces et données réelles

- La table `public.clients` ne comporte pas aujourd'hui de colonne d'attestation TVA ; aucun dossier d'exonération client valide n'a été chargé ou inventé.
- La table `public.erp_sku_fiscalite` ne contient aucune classification ; 7 SKU actifs étaient présents au dernier contrôle.
- La RPC `public.erp_sale_transaction` facture encore un taux global historique ; **elle ne lit pas les attestations client**. Le simulateur et le pont fiscal ne sont pas branchés à cette RPC.
- Le projet n'autorise pas l'application de `sql/013_facturation_parametree.sql` tant que le calcul du timbre et les cas fiscaux ne sont pas homologués.
- Les nouveaux modes `NORMAL` et `EXONERATION_CLIENT` sont calculés en mémoire uniquement ; aucun changement de schéma, GRANT, RLS ou donnée de production n'a été effectué ici.

## Suite technique

1. Conserver la CI verte et rejeter tout retour des taux réduits dans les modules Ventes.
2. Prévoir un référentiel sécurisé des attestations client **après** validation de la portée juridique, du contrôle des droits et du modèle des pièces justificatives.
3. Relier les attestations à des factures réelles uniquement après homologation des arrondis, des avoirs, remises, quittances/timbres, de l'idempotence et de la cohérence Python/PostgreSQL.
4. Vérifier le déploiement Streamlit hébergé séparément des commits GitHub : sa visibilité demeure non confirmée.
