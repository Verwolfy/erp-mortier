# Bascule de la facturation réglementaire — préconditions opérationnelles

Dernière mise à jour : 2026-11-09. **État : NON ACTIVABLE en production.**

## Situation constatée dans `main`

- `modules/ventes/service.py` conserve `TAUX_TVA=Decimal("0.19")`, `TAUX_TIMBRE=Decimal("0.01")`, `MAX_TIMBRE=Decimal("2500.00")`. `_totals` et `calculer_montants_facture` utilisent ces conventions ; `create_facture_brouillon` transmet leurs montants à `erp_sale_transaction`.
- `core/fiscalite_facturation.py` propose un calcul pur distinct, qui exige des paramètres datés, en vigueur et confirmés. Il ne détermine pas l'assujettissement d'un SKU.
- `sql/013_facturation_parametree.sql` porte explicitement la mention « BROUILLON : NON APPLICABLE ». Le brouillon bloque désormais les versions fiscales concurrentes ou non confirmées et refuse les factures en espèces à cause du timbre de quittance. **Il ne classe toujours pas la TVA par SKU et ne doit pas être appliqué en production.**
- La base production `wenydirqtmkywbxbxfal` contient 2 taux TVA de référence (`en_vigueur`) et 3 références CNAS (`a_confirmer`). Le **9 novembre 2026**, 145 SKU sont actifs : 2 lignes `erp_sku_fiscalite` en `A_VALIDER`, aucune `VALIDEE` applicable, soit 145 SKU non qualifiés. Résultat et code exact de l'audit dans `docs/FISCAL_READINESS_20261109.md`.
- Une référence TVA générale n'autorise pas l'application indistincte à chaque facture. Les règles de timbre d'encaissement ne doivent pas être déduites de l'ancien 1 % plafonné.

## Règles non négociables avant activation

1. Identifier, pour l'entreprise, régime fiscal réel / IFU et dates d'effet sur preuve documentaire.
2. Qualifier chaque SKU actif et ses opérations : normal / réduit / exonéré / hors champ, avec texte légal, source, date d'effet et contrôle d'un second validateur.
3. Déterminer les règles de timbre selon paiement et pièce juridiquement taxable, avec exceptions et source officielle datée.
4. Définir et valider explicitement le code de calcul applicable par opération ; si un élément manque, refuser le calcul avec message précis.
5. Maintenir la concordance Python / RPC SQL : montants `Decimal`, arrondis, remise globale, avoirs, dates et règles, sans taux implicite.
6. Tester en environnement isolé le flux facture brouillon → validation → règlement → rapprochement → écriture, avec idempotence `operation_id`, absence de doublons et aucune modification de facture validée.
7. Revoir l'impact de `sql/013_facturation_parametree.sql` sur la RPC actuelle, l'autorisation `SECURITY INVOKER`, les GRANT et l'accès effectif, avant d'en faire une migration de production.

## Travaux automatisables sans hypothèses métier

- Ajouter des tests du moteur pur avec fixtures explicites et dates antérieures/postérieures au changement.
- Préparer un service de lecture des paramètres et classifications avec rejet des états `a_confirmer` / `projet`.
- Ajouter un contrôle de correspondance entre montants calculés et montants retournés par la RPC, avant la bascule.
- Isoler puis supprimer les constantes réglementaires historiques **dans la même livraison validée que la nouvelle RPC**, pour éviter un décalage entre Python et SQL.

## Critère de livraison

Aucun taux, timbre, comptabilisation SCF ou déclaration ne doit être activé par simple présence d'un référentiel de base. Publication seulement après les scénarios SQL/Python vérifiés, l'absence de divergences de permissions, la qualification des produits concernés et la revue réglementaire.

## Sources projet

- `docs/REFERENTIELS_OFFICIELS_2026.md`
- `docs/ETAT_AVANCEMENT.md`
- `modules/ventes/service.py`
- `core/fiscalite_facturation.py`
- `sql/013_facturation_parametree.sql`

## Contrôle direct de la RPC production — 29 octobre 2026

Lecture seule de `pg_get_functiondef(public.erp_sale_transaction)` sur le projet `wenydirqtmkywbxbxfal` :

- `v_tax := round(v_net_ht * 0.19,2)` dans la branche `DRAFT` ;
- `v_stamp := ... round((v_net_ht+v_tax)*0.01,2),2500` pour le paiement en espèces ;
- `factures.taux_tva` est alimenté par la constante `0.19` à l'insertion.

**Conclusion technique :** la RPC réellement installée applique toujours les trois conventions fiscales historiques. Le calcul Python `core/fiscalite_facturation.py` fondé sur `TVA_VENTE_TAUX` ne peut pas être raccordé à cette RPC sans changement transactionnel coordonné, migrations testées et classification effective des SKU. Une réussite du CI du code ne démontre pas la conformité fiscale de la RPC installée.

**Mise à jour 9 novembre 2026 :** la requête de diagnostic de volume SKU a été exécutée avec succès en lecture seule, après ce contrôle historique. Résultat : 145 SKU actifs, 145 sans classification fiscale `VALIDEE` applicable, 2 dossiers `A_VALIDER`. Voir `sql/audits/fiscal_sales_readiness_readonly_20261109.sql`. Aucune mutation SQL effectuée.
