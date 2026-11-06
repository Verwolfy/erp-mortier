# Lot 048 — Export transactionnel des coûts industriels validés
Date : 6 novembre 2026

## Résultat : déployé sur TEST et production, contrôles réussis
- Dépôt `Verwolfy/erp-mortier`, branche `main`.
- Supabase TEST : `ffuhbmcfyexsbjwhryvj`; PROD : `wenydirqtmkywbxbxfal`.
- Migration `sql/043_export_couts_valides_snapshot.sql`, nom Supabase `erp_cost_validated_snapshot_export_20261106`, appliquée avec `success=true` sur les deux bases.
- Workflow ERP final : [succès](https://github.com/Verwolfy/erp-mortier/actions/runs/42234034189) avec **2 631 tests passés, 7 ignorés, 133 warnings**.
- Workflow audit de réconciliation : [succès](https://github.com/Verwolfy/erp-mortier/actions/runs/42234034167).
- Commit validé `d709e20f70e1172ffbc1b00ef7b3be8ea23fbb64`.

## Contenu technique
### PostgreSQL
- `public.erp_cost_export_validated(text)` : fonction `STABLE SECURITY DEFINER` avec `search_path=pg_catalog,public`, lecture seule et exposition REST réservée au `service_role`.
- Une seule RPC côté HTTP ; les sélections internes de la fonction STABLE lisent un instantané cohérent sous le snapshot MVCC de l'instruction.
- Export exclusivement sur une période `VALIDE` existante et non sur un brouillon.
- Contrôles : au moins un pool, une assiette et un OF capturé ; borne 5 000 pools, 5 000 OF et 10 000 assiettes ; cohérence `sum(pools.montant_dzd)=sum(snapshot.charges_imputees_dzd)` à une tolérance de 0,00001 DZD ; preuve SCF valide et débit suffisant pour chaque pool.
- Le JSON inclut métadonnées de période, totaux, pools et pièces SCF associées, instantanés OF capturés lors de la validation, assiettes.
- Les montants DZD et quantités sont sérialisés en **chaînes décimales PostgreSQL exactes**, pas en nombres flottants JSON.
- Aucune écriture comptable ni mouvement de stock.

### Service / Streamlit
- `modules/production/cost_service.py` : `export_validated_period(period_id)`, avec contrôles des deux droits de lecture Production et Finance et validation de la structure reçue.
- `modules/production/cost_views.py` : préparation explicite et téléchargement JSON réservés à une période `VALIDE`; message précisant qu'il s'agit d'un export **analytique, non d'une certification comptable légale**.
- Pas de téléchargement lancé automatiquement à la consultation d'un onglet.

## Tests réels sur Supabase TEST
- Migration : `success=true`.
- Script `sql/test_isole/20261106_export_transactionnel_048_ROLLBACK.sql` : verdict **`COST_EXPORT_SNAPSHOT_OK`**.
- Fixtures : 2 OF fictifs, 2 pools / pièces SCF valides, 4 assiettes.
- Chiffres : 70 DZD sur OF1, 140 DZD sur OF2, total 210 DZD.
- Vérifications : brouillon refusé, export validé conforme, champs numériques au format chaîne, preuves SCF présentes, deux snapshots, valeurs figées inchangées après modification du coût direct d'un OF fictif.
- Après ROLLBACK, contrôle indépendant : 0 OF, 0 période, 0 pool, 0 snapshot et 0 pièce SCF fictifs.
- Permissions : `anon` EXECUTE=false, `authenticated` EXECUTE=false, `service_role` EXECUTE=true.

## Production vérifiée après déploiement
- Migration : `success=true`.
- `periodes=0`, `charges=0`, `instantanes=0`, `preuves=0`.
- Fonction export présente et permissions conformes (clients directs refusés).
- Aucune donnée fictive importée, aucun impact CUMP, stocks, SCF.

## Limites
- Cet export est une restitution analytique bornée, cohérente à l'instant de la RPC. **Ce n'est pas un document comptable légal certifié** et ne prouve pas l'éligibilité industrielle des dépenses.
- Les coûts OF inclus sont les **instantanés de validation**, pas les valeurs courantes ; une dérive peut être signalée par la vue séparée `erp_cost_of_validation_drift`.
- 7 tests ignorés et 133 avertissements CI non qualifiés individuellement.
- Test navigateur authentifié avec vrai compte Production+Finance et compte limité : non réalisé. Les tests UI sont automatisés avec doublures.
- Aucun export de période réel n'a été réalisé puisque la production ne possède ni période validée ni pièce SCF validée.
- Volume dépassant le plafond => refus et futur mode de streaming/extraction dédiée plutôt qu'un JSON tronqué.

## Étape suivante
- Qualifier le parcours de téléchargement dans une vraie session Streamlit autorisée.
- Si exports très volumineux requis, concevoir un export serveur paginé à snapshot matérialisé et checksums.
- Contrôle métier Finance de l'éligibilité des lignes SCF.
