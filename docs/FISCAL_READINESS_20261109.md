# FISCAL-READINESS-01 — Passage de constantes historiques vers règles datées

**Contrôle du 9 novembre 2026 — production Supabase `erp-mortier`**  
**Statut : NON PRÊT pour le basculement de la facturation.**

## 1. Diagnostic réellement exécuté

Requête versionnée : `sql/audits/fiscal_sales_readiness_readonly_20261109.sql`. Elle a été exécutée **en lecture seule** sur le projet Supabase `wenydirqtmkywbxbxfal`. Aucun `INSERT`, `UPDATE`, `DELETE`, DDL, migration ou changement de permission effectué.

| Indicateur | Valeur constatée au 9 novembre 2026 |
|---|---:|
| Taux général TVA normal confirmé applicable | 1 |
| Taux général TVA réduit confirmé applicable | 1 |
| Taux spécifique de l'ancien moteur `TVA_VENTE_TAUX` | 0 |
| SKU actifs dans `sku_conditionnement` | **145** |
| SKU actifs sans classement TVA `VALIDEE` applicable | **145** |
| Lignes de `erp_sku_fiscalite` | 2 |
| Classifications `A_VALIDER` | 2 |
| Classifications `VALIDEE` applicables | **0** |
| Fonction `erp_facture_parametre(text,date,text)` en production | Non |
| Fonction `erp_sale_transaction(text,text,jsonb)` en production | Oui |
| Littéraux fiscaux anciens dans `erp_sale_transaction` | Oui |
| Autorisation automatique d'homologation | **Non, toujours** |

Les deux taux généraux de TVA datés disponibles sont une **référence du registre**, pas une preuve de classification juridique des 145 SKU. Aucune catégorie ni exemption ne peut être déduite automatiquement de ces taux.

## 2. Architecture Python existante — conserver un moteur unique

- `core/reglementation.py` : unique règle datée confirmée, contradictions `a_confirmer` applicables refusées.
- `core/classification_fiscale.py` : `selectionner_classification_bdd`, contrôle `statut=VALIDEE`, catégorie, code, source, justification, validateur, dates de vérification/validation, et validation au plus tard à la date d'opération.
- `core/precontrole_panier_fiscal.py` : tous les SKU du panier doivent avoir une classe datée valide.
- `core/liaison_tva_sku.py` : pont TVA/client/SKU de prévalidation ; le périmètre métier Ventes actuel accepte uniquement `NORMAL`. **Ne pas ouvrir `REDUIT`, `EXONERE` ou `HORS_CHAMP`** sans régime et classification juridiquement validés.
- `core/simulation_facture_tva_lignes.py` : simulation sans écriture, refuse paiement espèces et remise globale non homologuée ; résultat `autorise_activation_facturation=False`.
- `core/audit_couverture_tva_sku.py` et `core/registre_qualification_sku.py` : inventaire et préparation du travail de qualification, **sans inscription automatique de classifications**.

Un prototype supplémentaire de simulation multi-taux a été temporairement ajouté puis **retiré** après découverte des protections de l'architecture existante, pour éviter un deuxième moteur contournant des validations métiers.

## 3. SQL versionné mais NON appliqué

Le fichier `sql/013_facturation_parametree.sql` reste explicitement un **brouillon interdit de déploiement**. Deux durcissements :

1. `erp_facture_parametre` compte désormais **toutes les versions du code applicables à la date**, avant d'évaluer unité, statut, confiance et justificatifs. Toute version contradictoire, non confirmée ou de mauvaise unité provoque un refus, plutôt qu'être silencieusement ignorée.
2. La fonction de vente candidate refuse `paiement_especes=true` et met le timbre à zéro pour les autres factures ; le timbre doit être traité sur le fait générateur de la quittance selon un régime vérifié.

**La migration 013 n'est pas applicable à la production** : elle calcule encore une TVA agrégée au lieu de sélectionner et tracer chaque classification SKU. Elle exige en outre une date fiscale `date_facture` absente du payload legacy `modules/ventes/service.py`. L'ancien SQL `sql/005_atomic_sales.sql` et la RPC en production contiennent toujours des valeurs historiques à retirer **ensemble**, après validation sur environnement isolé.

## 4. Vérifications et garde-fous

- Test statique `tests/test_facturation_sql_013.py` : refus des versions concurrentes, absence de timbre candidat sur facture, absence de DDL destructif.
- Test SQL read-only `tests/test_fiscal_sales_readiness_readonly.py` : une seule instruction `SELECT`, analyse `pglast`, aucun indicateur d'homologation automatique.
- Projet Supabase TEST `ffuhbmcfyexsbjwhryvj` observé **INACTIVE** le 9 novembre 2026 ; aucune recette E2E SQL ne peut être affirmée.
- Aucun taux juridique inventé, aucun statut `VALIDEE` attribué à un SKU, aucun rôle Supabase modifié, données `DEMO/SIM` conservées.
- Le comportement actuel du code Python legacy n'est **pas** qualifié juridiquement : les valeurs fiscales figées subsistent dans le service et la RPC réelle.

## 5. Suite recommandée (ordre)

1. Préparer la revue juridique des **145 SKU actifs** avec `core/registre_qualification_sku.py` ; enregistrer uniquement des décisions documentées et approuvées, sans automatiser les catégories.
2. Vérifier les régimes, justificatifs et dates des ventes, remises, avoirs et quittances auprès du responsable fiscal/expert-comptable algérien.
3. Ouvrir un bac TEST autorisé et isolé avant toute migration ; les coûts ou droits de sa réactivation ne sont pas présumés acceptés.
4. Réécrire `erp_sale_transaction` par ligne, avec classification SKU, taux daté et preuve immuable, en préservant l'idempotence et les contrôles de stock/compteur/facture ; aligner `modules/ventes/service.py` sur le payload testé.
5. Effectuer les tests TX/SEC/E2E et de non-régression avec taux datés fictifs dans TEST ; ensuite seulement une décision documentée sur la mise en production.

**Conclusion : code et diagnostic préparatoires renforcés ; bascule fiscale de production non effectuée.**
