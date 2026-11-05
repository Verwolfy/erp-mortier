# Preuves SQL : concurrence FIFO et double lettrage — 05/11/2026

## Périmètre
- Projet Supabase TEST : `ffuhbmcfyexsbjwhryvj`, statut `ACTIVE_HEALTHY` avant les essais, `SELECT 1` réussi.
- Projet principal `wenydirqtmkywbxbxfal` : **aucune écriture** pendant ces essais.
- Deux appels SQL `execute_sql` déclenchés en parallèle sur la base TEST pour chaque compétition; session A maintient la transaction pendant `pg_sleep(5)`.

## FIFO — deux sorties de 6 kg sur 11 kg
- PREP exécuté : réception ancienne 4 kg, récente 7 kg, dates de création forcées à J et J+1.
- Session A : succès. `result_payload` : `quantity_remaining=5`, `movement_count=2`, allocations de lots `4 + 2`.
- Session B : refus attendu **SQLSTATE 23514**, message `Stock global insuffisant`.
- AUDIT en base : `stock_mp=5`, `sorties_reussies=1`, `mouvements_sortie=2`, `total_lots=5`, `nb_lots=2`, `audit_ok=true`.
- Lots après tentative : ancien 0/4 kg, récent 5/7 kg.
- Rejeu du même `operation_id` : résultat identique sans nouvelle sortie.
- Rejeu contradictoire (6 kg devenant 5 kg) : refus **SQLSTATE 23505**.
- NETTOYAGE exécuté puis contrôle de six familles : matières, opérations, outbox, lots, mouvements, stock **0 partout**.
- Scripts : `sql/test_isole/20261105_concurrence_fifo_{PREP,SESSION_A,SESSION_B,AUDIT,NETTOYAGE}.sql`.
- Contrat statique créé : `tests/test_isolated_fifo_concurrency_contract.py` (résultat CI encore à vérifier).

## Lettrage — deux allocations de 70 DZD sur paiement et facture fictifs de 100 DZD
- PREP exécuté : client, banque, règlement de 100 DZD et facture `VALIDE` de 100 DZD, identifiants `IT26_LET_*` exclusivement.
- Session A : succès, montant alloué 70 DZD.
- Session B : refus attendu **SQLSTATE 23514**, message `Solde règlement incohérent ou insuffisant`.
- AUDIT : `allocations=1`, `lettrage_total=70`, `montant_alloue=70`, `montant_paye=70`, `operations_reussies=1`, `evenements=1`, `audit_ok=true`.
- Rejeu identique session A : même `lettrage_id`, pas de doublon.
- Rejeu contradictoire : appel **bloqué par contrôle de sécurité de l'outil**, résultat SQL **non vérifié**, ne pas le déclarer passé.
- NETTOYAGE exécuté puis contrôle de huit familles : clients, factures, règlements, comptes, lettrages, opérations, outbox, écritures **0 partout**.
- Scripts : `sql/test_isole/20261105_concurrence_lettrage_{PREP,SESSION_A,SESSION_B,AUDIT,NETTOYAGE}.sql`.
- Contrat statique créé : `tests/test_isolated_lettrage_concurrency_contract.py` (résultat CI encore à vérifier).

## Limites et étapes suivantes
- Les appels sont des RPC PostgreSQL sous `service_role`, **pas des tests RLS d'utilisateurs finaux**, ni des tests UI Streamlit authentifiés.
- Les tests Python CI restent à confirmer pour le HEAD correspondant.
- Vérifier la remise en pause du projet TEST.
- Exécuter une campagne API authentifiée et tests navigateur des neuf onglets, sans produire d'écritures réelles.
- Ne pas utiliser les données de simulation pour reporting légal ou fiscal; validation expert-comptable algérien avant usage réglementaire.
