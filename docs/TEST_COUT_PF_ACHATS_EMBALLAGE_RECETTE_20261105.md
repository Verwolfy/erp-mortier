# Campagne complète de calcul du coût du produit fini — 05/11/2026

## Résultat
**PASS — `PF_COST_OK`**, deux exécutions SQL intégrales sur Supabase TEST, dont la deuxième avec scénarios négatifs complémentaires.

## Environnements
- GitHub : `Verwolfy/erp-mortier`, branche `main`.
- Supabase TEST : `ffuhbmcfyexsbjwhryvj`, restauré, connecté et testé.
- Production : `wenydirqtmkywbxbxfal`, **aucune écriture**.
- Script SQL : `sql/test_isole/20261105_cout_pf_achats_emballage_recette_ROLLBACK.sql`.
- Garde-fous `Decimal` : `tests/test_cout_pf_achats_recette_contract.py`. Résultat CI non confirmé.

## Jeu fictif créé pendant la transaction (tout est annulé par ROLLBACK)
- 2 fournisseurs fictifs : matières premières et emballages.
- 3 références de stock : charge minérale A (kg), liant B (kg), sacs 5 kg (U).
- 1 produit fini fictif mortier (KG), 1 SKU SAC 5KG (facteur conversion 5, 1 sac par SKU).
- 4 commandes d'achat dont 2 de matières et 2 d'emballages, 4 bons de réception, 6 lignes de réception.
- 1 recette par kg fabriqué : charge A 0,6 kg, liant B 0,4 kg, **sans emballage dans les lignes de recette**.
- 2 OF : 4 sacs puis 2 sacs, chacun clôturé conformément, soit 6 sacs (30 kg).

## Vague 1 : achats / réception / production
| Article | Quantité reçue | Coût unitaire fictif | Valeur (DZD) |
|---|---:|---:|---:|
| Charge A | 100 kg | 10 | 1 000 |
| Liant B | 60 kg | 20 | 1 200 |
| Sac | 10 U | 3 | 30 |
| Total vague 1 | | | **2 230** |

La réception n'a pas accepté comme prix de valorisation les prix fictifs manipulés 999 et 777 transmis côté BR ; le prix de commande est resté la source comptable et les assertions CUMP ont réussi.

OF1 : 4 sacs × 5 kg = 20 kg de mortier, soit 12 kg charge A + 8 kg liant B + 4 sacs.
`12 × 10 + 8 × 20 + 4 × 3 = 292 DZD`. PF : 4 sacs, **73 DZD par sac**.

La clôture identique répétée n'a produit aucun nouvel événement OF ni second stock.

## Vague 2 : nouveaux achats, nouveau CUMP, deuxième OF
| Article | Quantité reçue | Coût unitaire fictif | Valeur (DZD) |
|---|---:|---:|---:|
| Charge A | 100 kg | 14 | 1 400 |
| Liant B | 40 kg | 30 | 1 200 |
| Sac | 10 U | 5 | 50 |
| Total vague 2 | | | **2 650** |

CUMP après consommation OF1 puis deuxième réception :
- A : `(88×10 + 100×14) / 188 = 570/47 ≈ 12,1276595745 DZD/kg`.
- B : `(52×20 + 40×30) / 92 = 560/23 ≈ 24,3478260870 DZD/kg`.
- Sac : `(6×3 + 10×5) / 16 = 4,25 DZD/U`.

Une tentative de clôturer OF2 avec **1 seul sac d'emballage pour 2 sacs produits** a été rejetée avec SQLSTATE `23514`.

OF2 conforme : 2 sacs × 5 kg = 10 kg, soit A 6 kg, B 4 kg et 2 sacs.
Coût non arrondi : `6×570/47 + 4×560/23 + 2×4,25 ≈ 178,6572617946346 DZD`.
Le coût OF2 arrondi est **178,66 DZD**, et le CUMP du PF en stock après 6 sacs est :
`(292 + 178,6572617946346) / 6 ≈ 78,44287696577243 DZD par sac`.

## Réconciliation finale
- Stock MP A : 182 kg ; MP B : 88 kg ; emballages : 14 U ; PF : 6 sacs.
- Coût total des achats : **4 880 DZD**.
- Valeur des MP/emballages restantes : ≈ **4 409,342738205365 DZD**.
- Valeur du PF fabriqué : ≈ **470,657261794635 DZD**.
- Conservation : `stock MP restant + stock PF = 4 880 DZD` (tolérance numérique `1e-8`).
- SQL : `[{"verdict":"PF_COST_OK","campagne":"2 fournisseurs, 3 MP dont emballage, 4 achats, 4 receptions, 1 recette, 2 OF, 6 sacs","persistance":"ROLLBACK - fixtures non conservees"}]`.

## Nettoyage / non-persistance
La campagne utilise **BEGIN / ROLLBACK**, jamais COMMIT. Après la seconde exécution, un SQL indépendant a trouvé **0** ligne sur 11 catégories :
`fournisseurs, matieres, produits, sku, commandes, receptions, achats_ops, prod_ops, stock_mp, stock_pf, lots`.
Aucune donnée fictive persistée en TEST ni en production.

## Limites de couverture
Le calcul vérifie **le coût de revient direct matières + emballages**, et non le coût complet industriel : la fonction actuelle de clôture OF n'intègre pas dans ce scénario la main-d'œuvre, énergie, rebuts, amortissements, frais indirects ou frais d'approche. Ni les règles réglementaires d'arrondi/fiscalité ni les autorisations API/RLS ne sont certifiées.
Les assertions SQL ont réussi, mais le workflow CI GitHub n'a pas encore été confirmé.
Ne pas utiliser les valeurs fictives comme données comptables réelles.

## Suite
1. Vérifier la mise en pause de Supabase TEST jusqu'à `INACTIVE`.
2. Vérifier la CI pour le commit `main`.
3. Étudier l'intégration explicite et justifiée de coûts industriels supplémentaires, sans les inventer.
4. Vérifier les calculs depuis l'interface Streamlit avec un utilisateur authentifié.
