# Revue des 7 SKU de PRODUCTION — 31 octobre 2026

**Document de travail non homologué.** Source factuelle : Supabase PRODUCTION `wenydirqtmkywbxbxfal`, lecture des tables `public.sku_conditionnement` et `public.erp_sku_fiscalite` du 31 octobre 2026. Aucun taux fiscal n'est déduit du nom commercial ni du conditionnement.

| SKU | Produit | Format réel | Unité | Classification fiscale enregistrée |
|---|---|---|---|---|
| SKU-001 | PF-001 | Sac 25kg | SAC | Aucune |
| SKU-002 | PF-002 | Sac 25kg Façade | SAC | Aucune |
| SKU-003 | PF-003 | Sac 5kg Joint Blanc | SAC | Aucune |
| SKU-004 | PF-004 | Sac 25kg Mortier R4 | SAC | Aucune |
| SKU-005 | PF-005 | Fût 200L Adjuvant | FUT | Aucune |
| SKU-006 | PF-005 | Cuve IBC 1000L Adjuvant | IBC | Aucune |
| SKU-007 | PF-006 | Seau 20kg Peinture Satin | SEAU | Aucune |

**Résultat vérifié : 7/7 SKU actifs, 0 ligne dans `public.erp_sku_fiscalite`.** Aucun justificatif fiscal, catégorie, habilitation ni taux n'a été créé.

## Parcours de qualification autorisé

1. Rassembler la fiche technique, la composition, la désignation et l'usage réel de chaque SKU.
2. Identifier le régime applicable à l'entreprise et les textes algériens opposables à la date, sans supposer qu'une seule catégorie couvre tous les formats.
3. Faire valider par le responsable fiscal habilité la catégorie, le code de paramètre, la source juridique, la justification et la période d'effet.
4. Contrôler les droits, le calcul des lignes, les éventuelles attestations client et la facturation atomique. Un dossier classé n'autorise pas à lui seul la mise en production du taux à 0 %.

## Livrables applicatifs

- `modules/admin/qualification_sku_service.py` : lecture sécurisée du catalogue et de la couverture documentaire, sans écriture.
- `modules/admin/views.py` : nouvel onglet **Qualification TVA SKU**, réservé à `SECURITY_MANAGER`; export Markdown lorsque aucun dossier de classification n'est enregistré.
- `tests/test_qualification_sku_service.py` : tests de refus des données incohérentes, accès privé et absence d'activation fiscale.
- `core/registre_qualification_sku.py` : registre pur préexistant, sans taux et sans source inventée.

**Déploiement :** ces fichiers sont sur GitHub `main`. La présence de l'écran sur l'hébergement Streamlit n'est pas encore démontrée. Le verrou transactionnel 032 reste en place sur Supabase PRODUCTION. Aucune migration SQL supplémentaire n'est nécessaire pour cette revue en lecture seule.

La politique opérationnelle reste **une seule branche `main` et une seule base active PRODUCTION**, sans réactiver `erp-mortier-test`.
