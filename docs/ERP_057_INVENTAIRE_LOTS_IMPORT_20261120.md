# ERP-057 — Inventaire par lot, import Excel atomique et qualification des écarts
Date : 20 novembre 2026. ERP : `Verwolfy/erp-mortier`, branche `main`.

## Résultat réel
Le module ERP-056 a été prolongé sur la **base Supabase principale** `wenydirqtmkywbxbxfal` et dans l'interface Streamlit, sans modifier aucune quantité de stock ni aucun coût comptable.

- **Lots** : les lots présents dans `public.lots` sont photographiés dans la **même transaction** que la création d'une campagne, avec statut, péremption et quantité de départ ; leur comptage est séparé du comptage global de l'article. Les lots doivent tous être comptés avant soumission.
- **Rapprochement** : le système compare stock théorique agrégé, somme des quantités théoriques des lots et somme des quantités physiquement comptées. Une validation finale est refusée si les lots ont changé depuis la photographie, si des lots sont apparus, si les quantités globales et leurs lots divergent ou si des stocks positifs ne sont pas tracés.
- **Excel** : modèle vierge aux couleurs NEXTGEN, lié à un identifiant de campagne, puis import .xlsx contrôlé (un seul onglet, quatre colonnes strictes, identifiants textuels, sans formule, max. 2 Mo et 500 comptages/import). Les quantités non remplies sont ignorées. Les doublons, SKU hors campagne, nombres invalides et écarts sans motif sont refusés **avant écriture**. L'interface prévisualise le lot de comptages.
- **Atomicité et reprise** : `erp_inventory_bulk_count` revérifie toutes les lignes côté PostgreSQL, met à jour le lot en une seule transaction, et conserve une clé d'import déterministe dans `erp_inventaire_import_operations`. Un timeout peut être repris avec le même fichier ; une seconde charge sous la même clé est rejetée.
- **Écarts** : classification documentaire `PERTE`, `CASSE`, `PERIME`, `RETOUR_CLIENT`, `ERREUR_COMPTAGE`, `AUTRE`, dans le seul état `OUVERT`. La qualification exige une justification ; `PERTE/CASSE/PERIME` correspondent aux manquants et `RETOUR_CLIENT` uniquement à un excédent physique. Un changement de quantité annule toute qualification antérieure. Aucune décision fiscale ne découle du motif.
- **Dossier de régularisation** : export Excel/CSV/PDF **NON EXÉCUTABLE** exposant les écarts théoriques, la nature documentée, les PMP réels, les manques de lots, les pièces manquantes et les blocages. Aucun mouvement d'entrée/sortie, aucune modification des lots, aucun rapprochement SCF ni avoir fiscal n'est déclenché.

## Migrations principales (toutes appliquées)
1. `sql/ERP_057a_lots_import_atomique_20261120.sql` : 2 tables (lots snapshot et journal d'import), un trigger de capture, RPC de comptage lot et import idempotent. Tables RLS et service_role exclusivement.
2. `sql/ERP_057b_inventaire_gardes_lots_20261120.sql` : garde de soumission et approbation, vérifie les lots et la couverture de tous les articles.
3. `sql/ERP_057c_qualification_ecarts_20261120.sql` : classification documentaire et invalidation automatique au recomptage.
4. `sql/ERP_057d_justification_comptage_unitaire_20261120.sql` : RPC unitaire exige une justification même hors interface.

**Sécurité vérifiée** : RLS active, `anon` et `authenticated` n'ont ni SELECT sur les 2 tables, ni EXECUTE sur les RPC de lot/import/qualification ; seul `service_role` peut y accéder, et les RPC revérifient les droits métier Stocks et l'acteur ERP actif. Le conseiller Supabase `rls_enabled_no_policy` est INFO attendu car les tables internes ne sont pas exposées aux utilisateurs web ; pas de WARN/ERROR nouveau identifié.

## Tests transactionnels réellement réalisés
Sur le Supabase principal, mais entièrement annulés via `ROLLBACK` :
- Campagne PF : photographie des 3 lots PF, import atomique de 146 comptages, rejeu identique idempotent, doublon rejeté, 3 lots comptés, soumission et **approbation bloquée** à cause d'une lacune de traçabilité.
- Campagne MP : contrôle réel d'écart négatif, qualification `PERTE`, rejet d'un `RETOUR_CLIENT` incompatible, remise de classification à `NON_QUALIFIE` après recomptage.
- RPC unitaire : écart sans justification refusé ; justification valide acceptée dans la transaction annulée.
- Après tests : **0 campagne, 0 ligne, 0 lot de campagne, 0 import de test**.

Invariants base : 115 lignes `stock_actuel`, 146 `stock_actuel_pf`, 14 mouvements MP, 6 PF, 0 écriture SCF et 0 qualification SKU fiscale VALIDEE, inchangés par ERP-057.

## Écart de traçabilité diagnostiqué
Dans le registre actuel :
| Article | Stock ERP | Quantité lot identifiée |
| --- | ---: | ---: |
| `DEMO26_MP2` | 220 | 0 |
| `DEMO26_SKU2` | 60 | 0 |

Aucun lot fictif ajouté. Ces stocks empêchent de qualifier automatiquement une campagne complète « sans écart ». Les corrections doivent suivre une procédure physique justifiée.

## Limites métier, volontaires
- Pas de référentiel de dépôt/emplacement dans le schéma actuel : **aucune ventilation par dépôt n'est inventée**. Les campagnes restent globales MP/PF/SKU et par lot.
- Un seul compte ERP `ADMIN` actif constaté : **l'approbation indépendante reste impossible** avant création légitime d'un autre compte habilité.
- Aucun mouvement de régularisation automatique, même après double validation. Des pertes et retours clients demandent la traçabilité physique par lot, le contrôle qualité et les pièces comptables/fiscales réelles.
- Exports de consultation non certifiés SCF ; les modèles Excel n'autorisent pas l'import de formules.
- La version Streamlit hébergée n'a pas été confirmée à jour ; issue [#78](https://github.com/Verwolfy/erp-mortier/issues/78), et crédits TinyFish auparavant insuffisants. Aucun test E2E hébergé affirmé.

## Tests et emplacements de code
- `tests/test_erp057_inventory_lots_import.py` : modèles XLSX, validation, clés de reprise, contrôles de lots, non-écriture de stock, classification, dossier non exécutable.
- `modules/stocks/inventory_excel.py` : modèle et parser Excel.
- `modules/stocks/inventory_service.py` : RBAC serveur frais, import RPC, lots, comptages et classification.
- `modules/stocks/inventory_adjustment.py` : projet de régularisation purement consultatif.
- `modules/stocks/inventory_views.py` : nouvelle interface lot/import/qualification/exports.
- `modules/stocks/views.py` : accès via Stocks → Inventaire & Régularisation.

## Reprise prioritaire
1. Vérifier CI et audit GitHub sur **le dernier SHA du main** après les commits de documentation ; ne pas déduire l'état de runs annulés.
2. Confirmer le déploiement Streamlit effectif, puis tester le menu avec deux comptes ERP réellement habilités distincts.
3. Résoudre les 2 stocks positifs sans lot par justificatifs physiques, sans créer de lots DEMO fictifs.
4. Spécifier le référentiel de dépôts, transferts, statuts de lots et la RPC de **régularisation réelle** atomique et idempotente, sans activation prématurée : [issue #83](https://github.com/Verwolfy/erp-mortier/issues/83).
5. Préserver les garde-fous fiscaux et SCF existants (issue #76) ; un retour physique ne génère pas d'avoir automatiquement.
