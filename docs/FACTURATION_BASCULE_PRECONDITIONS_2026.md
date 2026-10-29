# Bascule de la facturation réglementaire — préconditions opérationnelles

Dernière mise à jour : 2026-10-29. **État : NON ACTIVABLE en production.**

## Situation constatée dans `main`

- `modules/ventes/service.py` conserve `TAUX_TVA=Decimal("0.19")`, `TAUX_TIMBRE=Decimal("0.01")`, `MAX_TIMBRE=Decimal("2500.00")`. `_totals` et `calculer_montants_facture` utilisent ces conventions ; `create_facture_brouillon` transmet leurs montants à `erp_sale_transaction`.
- `core/fiscalite_facturation.py` propose un calcul pur distinct, qui exige des paramètres datés, en vigueur et confirmés. Il ne détermine pas l'assujettissement d'un SKU.
- `sql/013_facturation_parametree.sql` porte explicitement la mention « BROUILLON : NON APPLICABLE » et remplace une fonction SQL métier. **Ne pas lancer cette migration automatiquement sur la production.**
- La base production `wenydirqtmkywbxbxfal` contient 2 taux TVA de référence (`en_vigueur`), 3 références CNAS (`a_confirmer`), 25 comptes de nomenclature SCF ; aucune classification dans `erp_sku_fiscalite` lors de la lecture du 29/10/2026.
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
