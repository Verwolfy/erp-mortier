# Lot 10 — Qualification des SKU NextGen dans l'ERP

Date : 1 novembre 2026. Concerne le code uniquement. Base Supabase production consultée en lecture seule.

## Constat de production confirmé
- 50 produits FENEK actifs, 142 SKU actifs pour 49 produits ; référence PROOF-PU-SEAL sans SKU.
- 142/142 SKU sans prix, 142/142 SKU sans dossier fiscal.
- 7 kits sans quantité nette ; 48 SKU liquides sans conversion masse validée.
- 97 matières candidates actives, sans fournisseur enregistré. 0 fiche publique dans site_products.
- Les historiques de 7 anciens SKU sont préservés, et leur statut demeure inactif.

## Amélioration
- modules/admin/nextgen_readiness_service.py : lectures bornées dans les seules tables produits, sku_conditionnement, matieres_premieres et erp_sku_fiscalite.
- Vérification SECURITY_MANAGER avant tout accès aux données ; échec fermé sur absence, doublon ou troncature.
- Nouvelle section dans Administration > qualification fiscale : afficher les difficultés des références NextGen sans action de modification.
- Tests de refus de données incohérentes, privilèges, densités, kits et statut fiscal.

## Limite importante
- Ce tableau ne délivre PAS un droit de vente, de facture, de fabrication ou de publication.
- Il ne constitue PAS un verrou transactionnel SQL. Un audit des RPC et circuits de ventes reste nécessaire avant de garantir un blocage effectif.
- Les matières sont des familles candidates, pas des articles d'approvisionnement qualifiés.
- Aucune densité, recette, taux TVA, conditionnement PU-SEAL ou fournisseur inventé.

## Prochaines étapes
1. Confirmer le conditionnement du mastic PU-SEAL avant création SKU.
2. Fournir composants et quantité de chacun des 7 kits.
3. Fournir les fiches de densité des 48 SKU liquides pour les conversions.
4. Identifier les grades et fournisseurs des 97 matières.
5. Constituer preuves fiscales et tarifs pour les 142 SKU.
6. Vérifier Streamlit Cloud après déploiement de main ; le code fusionné ne garantit pas qu'il soit visible dans l'ERP hébergé.

## Production : actions non faites
- Aucune modification SQL, aucun changement de secret ou RLS, aucune donnée fictive, aucun déploiement forcé, aucune publication web.
