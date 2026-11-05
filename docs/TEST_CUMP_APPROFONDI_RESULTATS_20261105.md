# Rapport d'exécution — CUMP approfondi (05/11/2026)

## Portée
- Supabase TEST exclusivement : `ffuhbmcfyexsbjwhryvj`.
- GitHub `Verwolfy/erp-mortier`, branche `main`.
- Script versionné : `sql/test_isole/20261105_cump_approfondi_ROLLBACK.sql`.
- Test contractuel : `tests/test_cump_approfondi_contract.py` (exécution CI à vérifier).

## Audit initial
- `get_project` : TEST initialement RESTORING, puis `ACTIVE_HEALTHY`.
- `SELECT 1` : une ligne; aucune fixture `IT26_CUMP_*` préexistante.
- Fonction réelle : `public.erp_apply_stock_movement`.
- Formule d'entrée : `(quantité ancienne × CMP ancien + quantité reçue × coût de réception) / quantité totale`.
- Lors d'une sortie, le CMP reste mémorisé et le coût de sortie est `quantité × CMP` ; les lots sont décrémentés dans l'ordre FIFO.

## Première exécution
- Résultat : **échec A3** : `P0001: A3 FIFO mouvements observe 1, attendu 2`.
- Diagnostic : les deux réceptions ont reçu le même horodatage de création; le FIFO tranche ensuite par `lot_id`, ce qui ne garantit pas que le lot de 10 kg soit choisi avant celui de 20 kg. Ce n'était **pas une preuve d'erreur CUMP**.
- Correction du test : dates `2026-11-01 08:00:00` et `2026-11-02 08:00:00` explicitement fixées pour ces deux lots, commit `cbce6ee0c27c8b243fa12823149c9c100ad8ab65`.
- La première transaction échouée a été annulée, sans commit.

## Deuxième exécution : succès
Commande : `execute_sql` Supabase TEST avec le fichier SQL intégral (transaction `BEGIN ... ROLLBACK`).

Sortie :
```json
[{"verdict":"CUMP_TEST_OK","persistance":"ROLLBACK obligatoire"}]
```

Assertions couvertes :
- MP A : entrées `10 × 100` puis `20 × 130` → CUMP `120`.
- Sortie 12 → coût `1440`, quantité restante 18, CUMP toujours 120.
- Entrée `6 × 90` → quantité 24, CUMP `112.5`.
- Sortie complète → stock 0 et anciens lots épuisés.
- Entrée `5 × 55` après stock nul → CUMP réinitialisé à `55`.
- Sortie 2 → coût `110`, stock restant 3.
- Rejeu identique : retour identique sans mouvement ou outbox supplémentaire.
- Rejeu contradictoire : rejet `23505`.
- Sortie supérieure au stock : rejet `23514`.
- Coût explicite sur sortie, coût d'entrée négatif, quantité nulle : rejets `22023`.
- MP B : précision des décimales `0.1 × 0.1 + 0.2 × 0.2 = 0.05`, CMP attendu `1/6` à tolérance `1e-12`.
- PF : entrées `2 × 25`, `3 × 40` → CMP `34`; sortie 1.5 → coût `51`, stock 3.5.
- Comptage des 13 opérations et 13 événements de stock; contrôle des quantités globales contre les quantités des lots.

## Preuve indépendante d'absence de résidu
Requête de lecture seule exécutée **après** le test SQL avec `ROLLBACK` :
```
matieres=0, produits=0, sku=0, stock_mp=0, stock_pf=0,
lots=0, mouvements_mp=0, mouvements_pf=0, operations=0, outbox=0
```
Aucune fixture CUMP de test n'a été persistée.

## Limites
- Calcul vérifié par SQL métier sous contexte propriétaire SQL; tests navigateur, utilisateur authentifié et RLS non couverts.
- Pas de test CUMP de deux réceptions simultanées avec coûts distincts dans cette campagne.
- Le CMP numérique conservé en précision décimale n'établit pas à lui seul la règle de présentation et d'arrondi monétaire (à spécifier séparément).
- Ne pas présenter ce test comme une homologation comptable légale; validation d'un expert-comptable algérien avant exploitation réglementaire.

## Suite
1. Confirmer l'état `INACTIVE` de TEST après demande de pause.
2. Vérifier la CI sur le SHA exact de `main`.
3. Ajouter un test concurrent de réceptions à prix distincts et un audit de valorisation de stock, si nécessaire.
