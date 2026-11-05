# Tests transactionnels isolés — ERP Mortier — 5 novembre 2026

## Périmètre et garanties

**Demande :** tester réellement les procédures d'achat, réception, fabrication, qualité, ventes et finance avec les transitions et les garanties d'idempotence, **sans altérer Supabase de production**.

- Projet dédié de test : `erp-mortier-test`, **`ffuhbmcfyexsbjwhryvj`**. Statut initial `INACTIVE` ; restauration demandée et accomplie avant essais.
- Production de référence : **`wenydirqtmkywbxbxfal`**, **AUCUNE RPC d'écriture ni modification de privilège sur cette base** pendant la campagne.
- SQL exécuté avec le rôle `service_role` (appel réel des fonctions PostgreSQL), dans une transaction explicite ouverte par `BEGIN` et terminée par `ROLLBACK`. Les éventuels droits `GRANT UPDATE` temporaires sont eux aussi annulés.
- Chaque script est versionné dans `sql/test_isole/`. **Ne jamais rejouer les scripts sur production.** La présence de la clause `ROLLBACK` protège aussi le projet de test contre les pièces définitives ; elle ne doit pas être remplacée par COMMIT.
- Aucun email, document officiel, déclaration fiscale, paiement bancaire externe ni processus d'authentification utilisateur n'a été déclenché.

## Résultats obtenus sur la base test (vraies fonctions, pas mocks)

| Lot | Script rejouable | Vérifications | Verdict SQL |
|---|---|---|---|
| Achats / stock MP | `20261105_test_achat_reception_RB.sql` | Créer commande 10 kg, retry identique, refus payload contradictoire, réception partielle 4 kg, réception finale 6 kg, deux replays stables, refus de sur-réception, statut final RECEPTIONNE, stock 10 kg et 2 entrées seulement | **ACHAT_RECEPTION_TRANSITIONS_IDEMPOTENCE_OK** |
| Recette / production / CQ / stock PF | `20261105_test_production_qualite_RB.sql` | Créer recette et OF avec retries stables, refus de payload recette contradictoire, PLANIFIE → EN_COURS → TERMINE, refus de redémarrage, clôture conforme OUI rejouable, consommation MP 2 kg et emballages 2 unités, stock PF 2, clôture contradictoire refusée ; deuxième OF EN_COURS → REJETE avec CQ NON et retry identique | **PRODUCTION_QUALITE_TRANSITIONS_IDEMPOTENCE_OK** |
| Commande / BL / facture / finance | `20261105_test_vente_finance_RB.sql` | Création commande client, replay + refus contradictoire, expédition de 2 SKU avec stock PF à zéro et retry, brouillon puis validation et retry, refus deuxième validation sous nouvel ID ; deuxième brouillon puis CANCEL/retry et refus double annulation ; création Banque + compte tiers client, paiement TTC 47,60 DZD avec écritures débit/crédit, replay, refus d'une deuxième référence bancaire, lettrage intégral et replay, refus de sur-lettrage | **VENTE_FACTURATION_PAIEMENT_LETTRAGE_IDEMPOTENCE_OK** |

**Interprétation :** les appels exécutent les RPC réellement installées dans le projet de test. Les doublons avec **même** `operation_id` et **mêmes** paramètres reprennent le résultat initial ; les paramètres incompatibles ou les actions interdites sont refusés. Aucun de ces tests ne représente une opération financière réelle.

## Contrôle de réversibilité

- Après les trois lots, contrôle **17 familles de tables/journaux** associées à `IT26_*` : **0 ligne résiduelle**, `rollback_clean=true`.
- Les permissions de test accordées provisoirement pendant les scripts sont redevenues leur état initial : `service_role` ne possède toujours pas UPDATE sur `produits`, `lignes_recette` et `clients` sur le projet de test.
- Contrôle lecture seule, après la campagne, de la base **production** : **80/80 lignes DEMO26** (`CONTROLE_80_LIGNES_OK`) et **40/40 lignes SIM26** dans 37 tables, stocks et montants du scénario inchangés. **120 lignes fictives conservées en production**, avec `sql/demo/20261105_rollback_TOTAL_120_lignes_FICTIVES.sql` non exécuté.

## Anomalies, corrections et limites

1. **Décalage des privilèges TEST vs PRODUCTION :** sur plusieurs tables référentielles, le rôle `service_role` de TEST a SELECT mais pas UPDATE ; les clauses `FOR SHARE` des RPC PostgreSQL nécessitent UPDATE. Sur PRODUCTION, les droits UPDATE comparés existent déjà. Les scripts de test réalignent **temporairement** les droits après BEGIN, avant les RPC, et les révoquent implicitement par ROLLBACK. **Le projet TEST n'a pas été aligné durablement** ; une campagne d'appels API hors transaction échouera tant que ce décalage ne sera pas réparé par une migration dédiée, revue et versionnée.
2. Correction du script de vérification de paiement : `ecritures_comptables` référence le paiement par `document_source_id`, et non par `reglement_id`. Cette correction a porté **sur le test uniquement**.
3. Tests exécutés **séquentiellement dans une seule session SQL par lot** ; l'idempotence est vérifiée, mais **pas une course concurrente depuis deux connexions**, ni un timeout réseau réel, ni les jetons/authentifications de l'interface.
4. Le parcours commandes → BL et le parcours facture client sont tous deux exercés, mais la RPC facture DRAFT impose un `commande_vente_id` absent : **aucune liaison directe commande/facture n'est créée par cette RPC**. Ne pas déduire du test que la facturation est attachée au bon de livraison ; ce point nécessite une spécification et un test fonctionnel supplémentaires.
5. Taux, montants et libellés utilisés sont exclusivement fictifs. Ce document ne valide aucune disposition comptable ou fiscale.

## Suite recommandée

- Réconcilier les privilèges `service_role` du projet TEST avec ceux de la production via migration SQL spécifique à TEST ; ne pas altérer les GRANT de production sans constat d'anomalie.
- Tester les appels RPC depuis **l'API et une session applicative autorisée** sur le projet TEST ; reproduire les courses simultanées (même `operation_id`, réceptions cumulées, référence de paiement unique) avec deux sessions indépendantes.
- Définir la liaison commerciale entre commande, bon de livraison et facture si elle est attendue ; la limitation SQL actuelle interdit l'attachement direct lors du brouillon.
- Vérifier les workflows GitHub tests ERP et audit sur le dernier commit documentaire, réparer tout échec confirmé.
- Conserver le rollback production et les données de démonstration pour les prochaines phases.

## Code de test

- [Achats et réceptions](https://github.com/Verwolfy/erp-mortier/blob/main/sql/test_isole/20261105_test_achat_reception_RB.sql)
- [Production et qualité](https://github.com/Verwolfy/erp-mortier/blob/main/sql/test_isole/20261105_test_production_qualite_RB.sql)
- [Ventes et finance](https://github.com/Verwolfy/erp-mortier/blob/main/sql/test_isole/20261105_test_vente_finance_RB.sql)
- [Garde-fous des scripts](https://github.com/Verwolfy/erp-mortier/blob/main/tests/test_isolated_rpc_smoke_contract.py)
