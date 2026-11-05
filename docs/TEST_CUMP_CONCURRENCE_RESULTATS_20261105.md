# CUMP — réception concurrente : résultats réels du 05/11/2026

## Environnement
- GitHub : `Verwolfy/erp-mortier`, branche `main`.
- Supabase TEST : `ffuhbmcfyexsbjwhryvj`, statut `ACTIVE_HEALTHY` pendant la campagne.
- Production `wenydirqtmkywbxbxfal` : **aucune écriture**.
- Scripts : `sql/test_isole/20261105_cump_concurrence_{NETTOYAGE,PREP,SESSION_A,SESSION_B,AUDIT}.sql`.
- Test contractuel : `tests/test_cump_concurrency_contract.py`; exécution CI non confirmée.

## Préparation
Contrôle SQL initial : 0 matière, 0 opération et 0 lot `IT26_CUMPR_*`.
Stock fictif initial : 10 kg à 100 DZD/kg, initialisation SQL réussie.

## Deux réceptions véritablement simultanées
Deux appels `execute_sql` lancés en parallèle sur TEST, avec `BEGIN/COMMIT` distincts et une session A maintenue ouverte pendant `pg_sleep(5)`.
- A : entrée 5 kg à 160 DZD/kg → réponse `quantity_remaining=15`.
- B : entrée 15 kg à 80 DZD/kg → réponse `quantity_remaining=30`.
- Toutes les deux ont réussi.

Audit SQL après concurrence :
```json
{"stock":"30","cump":"100.0000000000000000","somme_lots":"30",
 "nombre_lots":3,"entrees":3,"cout_entrees":"3000",
 "operations":3,"evenements":3,"audit_ok":true}
```
Oracle arithmétique indépendant :
`(10*100 + 5*160 + 15*80)/(10+5+15) = 3000/30 = 100 DZD/kg`.
Valeur de stock : `30 * 100 = 3000 DZD`.

## Rejeu et sortie valorisée
- Les deux `operation_id` de réceptions ont été rejoués sans erreur.
- Audit après rejeu : stock 30, CUMP 100, 3 lots, 3 mouvements, 3 événements ; **aucun doublon**.
- Un rejeu contradictoire de A, quantité 6 à la place de 5, est rejeté par `unique_violation` / SQLSTATE 23505 dans un bloc SQL de test.
- Sortie de 6 kg réalisée **dans une transaction terminée par ROLLBACK** : `cost_total=600`, `quantity_remaining=24`, CUMP inchangé 100, 1 lot consommé.
- Cette sortie n'a **pas** été conservée.

## Nettoyage et audit de résidus
Exécution de `20261105_cump_concurrence_NETTOYAGE.sql` : succès.
Contrôles SQL indépendants **après** nettoyage :
- `matieres_premieres` : 0.
- `stock_actuel` : 0.
- `lots` : 0.
- `mouvements` : 0.
- `erp_stock_operations` : 0.
- `erp_stock_outbox` : 0.

## Conclusion
**Validé pour les scénarios décrits** : les réceptions concurrentes de coûts distincts ne perdent pas de mise à jour, le stock et le CUMP se réconcilient, les lots et journaux sont cohérents, la valorisation d'une sortie reste stable, l'idempotence fonctionne.

Limites : ne constitue pas une certification comptable ni un test authentifié RLS/Streamlit; contrôler séparément arrondis monétaires réglementaires et la CI GitHub. Confirmer que la pause de TEST atteint `INACTIVE` après la campagne.
