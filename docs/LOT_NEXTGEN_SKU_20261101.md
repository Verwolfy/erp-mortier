# Lot ERP NextGen — Conditionnements, matières et SKU (2026-11-01)

## Décisions utilisateurs appliquées

- BOND : sacs 5, 10, 25 kg.
- PROOF : seaux 5/20 kg, bidons 5/20 L et kits pour résines, **selon compatibilité réelle du concept**.
- FLOW : bidons 5/20 L, fûts 200 L, IBC 1000 L.
- PAINT : seaux 5/10/20 kg.
- 97 matières candidates rendues actives dans `public.matieres_premieres`, **sans grade, fournisseur ou unité chimique inventés**.
- Articles d'emballage traités comme MP : 10 variantes actives, `unite_stock=U`, masse à vide et fournisseur non déterminés.
- Tous les SKU nouvellement créés sont actifs, avec stocks initiaux 0 et prix/valorisations NULL.

## Résultat transactionnel vérifié sur Supabase PROD

- Projet `wenydirqtmkywbxbxfal`.
- 142 nouveaux `sku_conditionnement` actifs couvrant 49 des 50 produits NextGen.
- Répartition : sacs 48, seaux 39, bidons 24, fûts 12, IBC 12, kits 7.
- 97 matières premières + 10 articles emballage = 107 références actives créées/activées.
- 142 lignes de stock produit et 107 lignes stock matière à quantité zéro ; coûts et valorisations laissés NULL.
- Les sept anciens SKU `SKU-001` à `SKU-007` sont `actif=NON`, **pas supprimés**.
- Aucune modification des anciennes factures, commandes, consommations, stocks historiques, recettes et ordres de fabrication.
- 50 fiches `site_produits` toujours privées, `statut_technique=brouillon`, `statut_commercial=valide` et `publie=false` ; 0 produit dans `site_products`.
- Audit des liens : 0 SKU sans produit actif, 0 référence emballage inexistante, 0 prix inventé, 0 conversion L→kg inventée, 0 stock non nul/valorisé.

## Exceptions et garde-fous de conformité

1. **FENEK-PROOF PU-SEAL** : aucun des formats confirmés n'est adapté de façon suffisamment justifiée au mastic. Pas de SKU créé. Choisir ultérieurement le conditionnement fournisseur (cartouche/poche ou autre) avec volume réel.
2. **Sept kits** : SKU catalogue actifs, sans quantité nette, composition de composants ou article d'emballage final. Leur activation administrative ne constitue pas une validation de fabrication ni une disponibilité commerciale.
3. **48 SKU liquides en litres** : `poids_net=NULL`, `facteur_conversion=NULL` jusqu'à confirmation de la densité et de l'unité de production. Ne jamais assimiler volume et masse.
4. **Fiscalité** : nouveaux SKU actifs mais TVA, classifications et tarifs non qualifiés. Ne pas effectuer de facturation de ces SKU avant validation fiscale et tarifaire par l'ERP.
5. **Matières** : 97 familles actives dans le référentiel, mais sans grade ni fournisseur, FT, FDS, HS, prix ou stocks physiques. L'activation ne certifie ni leur conformité ni leur disponibilité à l'achat.
6. **Documentation technique** : normes, FT/FDS, recette et documents de laboratoire restent non validés ; aucun nouveau document public.

## Preuve d'exécution

La première transaction a échoué sur un typage `NULL` du champ numeric, et **la base a été contrôlée intégralement inchangée** avant correction. La transaction corrigée a été exécutée avec succès et les post-vérifications confirmées.

SQL de traçabilité : `supabase_PROD_lot_sku_transaction.sql` (NE PAS RÉEXÉCUTER ; rejette les collisions). Registre : `NextGen_ERP_Sku_Emballages_Matieres_20261101.xlsx` et `manifest_sku_et_emballages.json`. Le fichier Excel est un **audit d'intégration**, non une certification d'achat ou de production.

## Prochaines actions

- Confirmer fournisseur/format précis de PU-SEAL et quantités unitaires des kits.
- Valider les densités pour gérer les conversions et les unités de production.
- Obtenir fiches fournisseurs/FT/FDS, codes douaniers vérifiés, prix d'achat, stocks physiques réels.
- Mettre en place les règles de qualification TVA et tarifs avant premières factures.
- Qualifier les produits au laboratoire avant publication web ou revendication normative.
