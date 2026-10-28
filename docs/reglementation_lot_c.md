# Lot C — moteur réglementaire (socle isolé)

Statut : **développé et testé isolément, NON intégré à la production**.

## Périmètre livré
- core/reglementation.py : sélection d'un paramètre réglementaire par code et date d'opération.
- Blocage des règles non confirmées, des projets, des sources absentes et des règles contradictoires.
- Calcul décimal générique traçable (assiette, taux, date, source, résultat).
- tests/test_reglementation.py : tests avec valeurs fictives, sans taux juridique codé en dur.

## Commande de tests
Depuis la racine du dépôt :
python -m pytest -q tests/test_reglementation.py

## Hors périmètre et blocages
- Pas de branchement aux factures, bulletins, déclarations ou interfaces Streamlit.
- Pas de lecture/écriture Supabase ou Google Sheets.
- Aucune règle algérienne n'a été certifiée à ce stade ; aucune valeur juridique n'est chargée.
- Avant intégration : auditer les sources officielles, créer les migrations SQL numérotées et leur suivi, garantir la cohérence SQL/Python, relancer les tests complets et mettre à jour Guide & Aide.
- Ne jamais recalculer une pièce fiscale ou sociale déjà validée en l'écrasant.
- Toute règle à fort impact doit être confirmée avant activation, conformément à la phase R du cahier des charges.

## Suite recommandée
1. Phase R : validation officielle et versionnement de la réglementation algérienne.
2. Lot C : registre SQL, lecture contrôlée et remplacement des taux codés en dur en Python **et en SQL**.
3. Lot D : plan comptable SCF et journaux.
4. Lot E : fiscalité et déclarations.
5. Lot F : paie, CNAS, CASNOS, IRG et bulletins.
