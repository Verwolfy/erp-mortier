# ERP-059 — Incident BL DEMO26_CV1 et protection des sorties FIFO
Date de l'incident : **20 novembre 2026**. Référentiel : `Verwolfy/erp-mortier`, branche `main`. Projet Supabase principal : `wenydirqtmkywbxbxfal`.

## Symptôme observé
L'écran `Ventes → Expédition / Bons de livraison` présentait :
- Commande client `DEMO26_CV1` (`EN_COURS`), SKU `DEMO26_SKU1` ;
- « reste 10 | stock PF 180 », demande de livraison 1 ;
- Message « Opération non confirmée. Vérifiez-la dans Supabase avant de réessayer. »
- ID de tentative : `SALE-UI-7b11a0b925a74262b72ddf3616083d5e`.

## Résultats SQL directs, lecture seule
- `erp_sales_operations` : **aucune ligne** sous cet ID ; il n'existe pas de preuve d'une nouvelle transaction de livraison.
- Commande `DEMO26_CV1` : commande de **10** unités `DEMO26_SKU1`.
- BL `DEMO26_BL1` : **10** unités, statut historique `LIVRE`, date `2026-11-03`. La commande est **déjà intégralement livrée selon ses BL**.
- `stock_actuel_pf` pour SKU : **180**, PMP **1000 DZD/SKU**.
- Lot `DEMO26_LOT2` : **180**, statut historique `DISPONIBLE`, expiration `2027-10-20`. La RPC `erp_apply_stock_movement` prélève en FIFO uniquement les lots `ACTIF`, soit **0 unité prélevable**.
- Le journal `mouvements_pf` ne porte pour ce SKU qu'une entrée `DEMO26_OF1` de 180 ; aucune sortie historique associée au BL DEMO, ce qui signale une incohérence des **données de démonstration**, non une preuve d'un nouveau débit.
- Les autres BL en base étaient `EXPEDIE`; `LIVRE` est un statut historique réel.

## Reproduction sous transaction annulée
Simulation `erp_sale_transaction('SHIP', ..., DEMO26_CV1 / SKU / 1)` dans `BEGIN...ROLLBACK` :
`SQLSTATE 23514 — Incohérence globale / somme des lots : opération annulée`.
**Aucun BL, lot, mouvement ni stock persisté par la simulation.**

## Causes identifiées
1. UI `_remaining_for_order` et RPC `erp_sale_transaction` comptaient les livraisons uniquement lorsque le BL était `EXPEDIE` ; le BL historique `LIVRE` était ignoré, entraînant un reste fictif de 10 et exposant à une double livraison.
2. UI affichait `stock_actuel_pf` (180) sans contrôler les lots `ACTIF` réellement éligibles à la RPC de sortie FIFO. Le lot existant était `DISPONIBLE`, donc la sortie échouait.

## Corrections exécutées
- `modules/ventes/views.py` : `_DELIVERED_BL_STATES={EXPEDIE,LIVRE,LIVREE,TERMINE}`; autres statuts historiques non reconnus bloqués, états annulés/brouillons exclus. Disponibilité FIFO ACTIF affichée et utilisée pour borner la quantité livrable ; aucun lot actif → formulaire bloqué.
- `modules/ventes/views.py` : les opérations `SALE-UI` restées `uncertain` sont **vérifiées en lecture seule** dans le journal SQL et les BL avant reprise, avec contrôle des droits frais, du contenu SKU/quantités, du stock et de la disponibilité FIFO. Si opération retrouvée et BL concordant → marquer confirmée sans nouvelle émission. Si opération absente ET demande non expédiable → permettre la clôture du dossier seulement après nouvelle vérification. Sinon, autoriser la reprise avec **exactement le même ID**, jamais une tentative neuve.
- Repère d'interface : `SOF-ERP-20261120-BL-RECONCILIATION-01` ; l'affichage du repère ne prouve pas le SHA de déploiement.
- `sql/005_atomic_sales.sql` : même protection côté RPC pour nouveaux environnements.
- `sql/ERP_059_bons_livraison_statuts_historiques_20261120.sql` : migration appliquée au principal via la fonction autoritative réellement installée, afin de **préserver tous les contrôles fiscaux préexistants**. Une version idempotente et ciblée est conservée en source pour les environnements à migrer, sans dupliquer les taux fiscaux anciens dans le dépôt.
- Aucune modification manuelle de `DEMO26_CV1`, `DEMO26_BL1`, `DEMO26_LOT2`, `stock_actuel_pf`, `mouvements_pf` ou `factures`.

## Preuves de protection SQL après migration
En transaction de contrôle `BEGIN ... correctif ... appel SHIP ... ROLLBACK`, une nouvelle expédition de 1 sur la commande déjà livrée est rejetée en amont de FIFO : `Quantité expédiée supérieure à la commande` (SQLSTATE `23514`).
- 1 BL préexistant, 0 opération de test enregistrée.
- Stock PF = 180, lot = 180 inchangés.
- RPC `erp_sale_transaction` : `anon` EXECUTE **false**, `authenticated` EXECUTE **false**, `service_role` EXECUTE **true**.
- Migration réellement appliquée et relue : inclusion des statuts `EXPEDIE,LIVRE,LIVREE,TERMINE` et garde états inconnus confirmées.

## Tests automatisés
- Tests dans `tests/test_ventes_views_security.py` : historique `LIVRE` empêche doublon, états `LIVREE/TERMINE` pris en compte, inconnus bloqués, lot `DISPONIBLE` non prélevable, reprise incertaine vérifiée, résultat SQL confirmé sans double appel, charge erronée refusée.
- Test `tests/test_010A_02D_02_ventes_crm_activity.py` actualisé pour le callback supplémentaire.
- Audit réglementaire : la migration source a été convertie en patch **ciblé** pour ne pas copier les constantes fiscales historiques. Ne jamais les ajouter à une liste de tolérance ni considérer ces constantes comme homologuées.
- **Consulter les deux derniers runs GitHub sur `main`** avant de déclarer CI verte : des runs intermédiaires ont échoué puis les causes ont été corrigées.

## Procédure utilisateur après déploiement Streamlit confirmé
1. Ouvrir Ventes → Expédition / Bons de livraison, dossier incertain `SALE-UI-7b11a0b925a74262b72ddf3616083d5e`.
2. Cliquer **Vérifier cette livraison dans Supabase (lecture seule)**.
3. Si le serveur confirme « Tentative absente du journal / commande déjà livrée », cliquer **Clore uniquement cette tentative non enregistrée**. **Ne pas cliquer Réessayer pour cette commande.**
4. Réconcilier le statut des lots DEMO et l'ancien BL avec le responsable métier, sans convertir `DISPONIBLE` en `ACTIF` ni insérer de faux mouvements. Ticket [#84](https://github.com/Verwolfy/erp-mortier/issues/84).
5. Vérifier que Streamlit affiche réellement `SOF-ERP-20261120-BL-RECONCILIATION-01`. Déploiement Streamlit non vérifié (issue [#78](https://github.com/Verwolfy/erp-mortier/issues/78)).

## Limites
La correction évite la surlivraison et les retries dangereux **sans fabriquer un historique cohérent**. Le stock DEMO 180 et le BL LIVRE 10 sans mouvement doivent être audités avant rectification physique. Aucun changement fiscal, SCF, aucune facture ou perte de lot créé par ERP-059.
