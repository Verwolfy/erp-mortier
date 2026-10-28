# Lot C — socle réglementaire algérien, état de développement

**Statut : PR #2 ouverte en brouillon, non fusionnée, non déployée ; aucun paramètre juridique activé.**

## Développement réalisé
- `core/reglementation.py` : sélection des taux unitaires validés par code et date d'opération, montants Decimal et traçabilité.
- `core/baremes.py` : moteur générique de tranches marginales avec sélection d'une seule version applicable ; refus des règles non vérifiées, des chevauchements, des valeurs invalides et des projets. Compatible avec le format JSONB `donnees.tranches`.
- `sql/012_reglementation_registre.sql` : **proposition de migration, non exécutée** : registres réglementaires datés, suivi de migrations avec empreinte, RLS sur les nouvelles tables et refus d'accès direct anon/authenticated.
- Tests locaux sur `tests/test_baremes.py` et `tests/test_reglementation_sql_012.py` : **40 réussis** ; la compilation du nouveau moteur réussit. Ce ne sont pas des tests PostgreSQL et la suite ERP complète n'a pas encore été exécutée.

## Format de données
Une entrée `regles_reglementaires` de type `progressif` contient dans `donnees` une liste `tranches` avec `jusqua` (borne supérieure ou null pour la dernière tranche ouverte) et `taux` (fraction décimale). L'algorithme applique les taux marginalement et arrondit une fois en fin de calcul. Les valeurs de test sont fictives et ne doivent jamais être présentées comme un barème IRG officiel.

## Contrôles obligatoires avant la mise en service
1. Audit des textes officiels et validation des paramètres fiscaux et sociaux ; aucun taux légal en dur.
2. Revue et tests SQL de la migration 012 sur **TEST**, incluant privilèges RLS. Son exécution nécessite l'accord distinct sur les modifications des droits ; ne pas toucher à la base principale.
3. Préparation d'un lanceur transactionnel des migrations avec empreinte SHA-256, contrôle du schéma et gestion d'erreur ; les tests statiques ne prouvent pas l'exécution SQL.
4. Brancher les services Finance, Ventes, RH à la source unique des paramètres ; remplacer **en même temps** TVA/timbre côté Python et SQL, sans casser les documents validés.
5. Préserver les changements locaux du Guide & Aide, README et de la sauvegarde Google Sheets avant toute réconciliation avec la branche.
6. Exécuter la suite complète de tests ERP, contrôler les secrets et vérifier la branche Streamlit déployée avant fusion/production.

Ces développements ne sont pas encore visibles dans l'application Streamlit.
