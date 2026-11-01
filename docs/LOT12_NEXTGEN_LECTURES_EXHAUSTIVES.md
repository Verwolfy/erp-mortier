# Lot 12 — Lectures NextGen exhaustives, bornées et contrôlées

Date : 1er novembre 2026 — **lecture seule, aucune homologation**.

## Défaut traité

La première version de `modules/admin/nextgen_readiness_service.py` appelait `range(0, limite)` une seule fois par table sans `count="exact"`. Si PostgREST ou un proxy imposait une limite plus petite, les SKU, matières ou enregistrements fiscaux au-delà de cette limite pouvaient être omis **silencieusement**. Le tableau semblait alors exhaustif, sans preuve.

## Correction

- Parcourir les quatre tables par pages de **100 lignes demandées au maximum**, avec `count="exact"`, ordre stable par clé primaire, et offset basé sur le nombre réellement reçu (utile lorsque le serveur renvoie une page de 17 lignes malgré 100 demandées).
- Refaire la vérification `require_security_manager()` **avant chaque requête** et interrompre si le droit a été retiré.
- Refuser une réponse sans total entier, un total changeant, une ligne dupliquée, une page prématurément vide, une quantité excédant le total ou les limites de sécurité propres à chaque table.
- Clés : `produits.pf_id`, `sku_conditionnement.sku_id`, `matieres_premieres.mp_id` ; la table `erp_sku_fiscalite` a la clé primaire **composée** `(sku_id, date_effet)`. La date d'effet est maintenant lue uniquement pour garantir le tri et l'unicité ; elle n'attribue pas une validité fiscale à elle seule.
- Aucun champ personnel, aucune clé ou secret supplémentaire. Les drapeaux `autorise_facturation` et `autorise_fabrication` restent toujours `False` ; aucune action de modification de données ni de RLS.
- Le CSV du lot 11 n'est produit que si les quatre lectures ont abouti en entier : sinon l'UI informe de l'indisponibilité et **ne propose pas d'export**.

## Tests de non-régression

- Simulation d'un backend limitant physiquement chaque page à 17 lignes pour 142 SKU ; le résultat complet doit contenir les 142, sans double compte.
- Variation du total exact entre pages, total absent, page vide intermédiaire, doublon fiscal sur clé composée, coexistence de plusieurs versions fiscales de dates différentes, retrait du droit entre deux pages.
- Maintien des tests métier et sécurité du lot 10/11 + suite complète CI sur PR.

## Limites honnêtes

Le décompte exact et les clés uniques identifient beaucoup de tronquages, mais **ne remplacent pas un snapshot transactionnel** de plusieurs tables. Des modifications concurrentes à cardinalité constante peuvent rester invisibles. Aucune capacité nouvelle de facturation, production, conformité ou publication n'est créée.

## Source SQL vérifiée

Base principale `wenydirqtmkywbxbxfal` consultée en lecture seule le 01/11/2026 : `pg_constraint` signale `PRIMARY KEY (sku_id, date_effet)` pour `public.erp_sku_fiscalite`.

## Prochaine étape

Valider la CI de la PR sur la branche, fusionner sur `main` sans écraser des évolutions concurrentes, valider à nouveau la CI de merge, puis vérifier la version hébergée en session Streamlit autorisée.
