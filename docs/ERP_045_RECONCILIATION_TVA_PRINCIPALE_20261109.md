# ERP-045 — Réconciliation TVA des SKU sur la base principale, 9 novembre 2026

## Contrainte permanente du projet

- **Seule branche distante GitHub :** `main`.
- **Base unique d'essais et d'exécution :** Supabase `erp-mortier`, projet `wenydirqtmkywbxbxfal`.
- **Supabase TEST** `ffuhbmcfyexsbjwhryvj` : demeure **INACTIVE**. Ne pas la restaurer ou créer un nouveau projet TEST.
- Les données actuelles servent aux essais, mais une classification fiscale, des taux et une attestation juridique **ne doivent jamais être fabriqués ou déclarés certifiés**.

## Migration réellement appliquée

- **Version native : `20261109142511`**.
- **Nom : `erp_045_tva_preview_reconciliation_registre_sku`**.
- **SQL GitHub** : `sql/045_tva_preview_reconciliation_registre_sku.sql`, versionné sur `main`.
- **Résultat de `apply_migration`** : `success: true`.
- La base principale possède désormais **35 migrations natives**, après ERP-044 (`20261109141222`) puis ERP-045.

## Correction architecturale

Une table `public.erp_sku_fiscalite` existait déjà et possédait les champs réglementaires attendus : SKU, date d'effet, date de fin, catégorie (`NORMAL`, `REDUIT`, `EXONERE`, `HORS_CHAMP`), code de référence, `statut`, source, justification, date de vérification, validateur et date de validation.

ERP-044 avait préparé une table `erp_sku_tva_qualifications` supplémentaire. ERP-045 **évite deux sources fiscales concurrentes** :

1. `erp_tax_preview_classified` lit **exclusivement `erp_sku_fiscalite`** pour obtenir la qualification du SKU. Il n'accepte que `VALIDEE` avec justificatifs complets et catégorie `NORMAL`/`REDUIT`; les catégories `EXONERE`/`HORS_CHAMP` nécessitent un moteur métier distinct.
2. Les lignes `A_VALIDER` applicables, chevauchantes, invalides ou sans justificatif provoquent un refus (fail-closed).
3. Le taux lui-même provient de `public.parametres_reglementaires` avec date, statut `en_vigueur`, confiance `CONFIRMEE` et unicité.
4. La table pilote ERP-044 demeure **vide**, annotée `OBSOLÈTE`, et ses droits `SELECT`/`INSERT`/`UPDATE` ont été retirés à `service_role`. Elle n'est plus utilisée par la RPC et n'a pas été supprimée.
5. La transaction de facturation active `erp_sale_transaction` et les factures historiques ne sont **pas** modifiées.

## Preuves exécutées et vérifiées

| Vérification | Constat |
|---|---|
| [PostgreSQL 17 jetable : ERP-044 puis ERP-045](https://github.com/Verwolfy/erp-mortier/actions/runs/42633745922) | **success**, données fictives et tests de classification canonique |
| [Tests ERP GitHub SHA `384cb5ac`](https://github.com/Verwolfy/erp-mortier/actions/runs/42633801815) | **success**, 3 236 tests, 0 échec, 1 avertissement |
| [Audit GitHub même SHA](https://github.com/Verwolfy/erp-mortier/actions/runs/42633801706) | **success** à la 2e tentative. Première tentative : échec fluctuant d'un test PDF NextGen sans rapport avec la fiscalité ; relance isolée réussie |
| Enregistrement DB | 35 versions, la dernière `20261109142511` |
| RPC SQL | Lit `erp_sku_fiscalite`, ne lit plus `erp_sku_tva_qualifications` |
| Privilèges | `service_role` : accès à la source canonique et exécution RPC ; `anon`/`authenticated` : pas d'exécution RPC |
| Table pilote | 0 ligne, pas de `SELECT` ni `INSERT` pour `service_role` |
| Qualification préexistante | 2 `A_VALIDER`, 0 `VALIDEE`, conservées intactes |

**Essai supplémentaire sur la base principale** : insertion temporaire d'une qualification explicitement fictive pour un SKU, sous `BEGIN`, appel de la RPC avec `SET LOCAL ROLE service_role`, vérification du montant calculé contre le registre et refus d'un `code_tva` client imposé, puis `ROLLBACK`. Résultat conforme. Nouveau contrôle après `ROLLBACK` : **2 dossiers préexistants, 0 validé, 0 trace de l'essai**. Aucune facture, aucun règlement, aucune écriture comptable.

## À faire

- Ne pas homologuer automatiquement les 145 SKU actifs. Les 2 dossiers actuels restent `A_VALIDER`; les autres SKU n'ont pas encore de dossier fiscal validé.
- Unifier l'interface de paramétrage autour de `erp_sku_fiscalite`, avec les validations humaines et sources juridiques pertinentes ; éviter l'usage de la table 044 neutralisée.
- Faire évoluer `factures` et `lignes_facture` pour gérer les taux TVA par ligne, remises globales, avoirs, exonérations et timbres sur quittance.
- Adapter `modules/ventes/service.py` et `public.erp_sale_transaction` de façon cohérente et atomique ; retirer ensuite les anciennes constantes, en protégeant idempotence, droits et stock.
- Exécuter les recettes et vérifier les résultats sur la **base principale d'essais**, sans jamais restaurer Supabase TEST.
- Les textes légaux et la classification fiscale doivent être validés par les responsables compétents avant toute déclaration réglementaire réelle.

**Statut :** ERP-044/045 réellement installées et contrôlées sur la base principale ; la refonte de la facturation transactionnelle reste ouverte.
