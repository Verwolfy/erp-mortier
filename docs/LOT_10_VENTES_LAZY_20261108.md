# LOT-10 — Ventes : cinq vues exclusives et lecture différée des factures

Date : 2026-11-08 ; branche `perf/lot10-ventes-lazy-20261108`.

## Avant

L'ouverture Ventes exécutait les cinq onglets `st.tabs` : Facture/Avoir, Commandes, Livraison, Suivi et contrôle TVA SKU. L'autorisation était contrôlée une fois, mais un vendeur déclenchait aussi `get_factures()` sur l'ensemble des vues alors que seules Facture/Avoir et Suivi utilisent la liste complète.

## Après

- `Vue Ventes` sélectionne un seul panneau après `_sale_access()`, qui conserve la lecture du compte et des droits frais côté serveur.
- `get_factures()` est appelé pour un profil habilité à écrire uniquement quand la vue est Facture/Avoir ou Suivi. Le suivi en lecture seule conserve sa pagination serveur stricte.
- Les panneaux Commandes, Livraison et TVA ne téléchargent pas toutes les factures.
- Les cinq fonctions métier existantes, les contrôles des factures et avoirs, la validation, les expéditions, les protections `operation_id`, la classification fiscale et les erreurs fermées restent inchangés.
- Huit nouveaux tests offline : un seul panneau, absence de prélecture factures, maintien de la validation complète, refus lecture, lecture seule et activité utilisateur.
- Aucun SQL, migration, RLS/GRANT, donnée ni identifiant réel modifié.

## Acceptation

Deux suites CI complètes sur la PR, puis deux sur `main` après fusion. Les gains démontrés portent sur les familles de chargements évitées, pas la latence réelle. Une recette authentifiée Ventes, TVA et avoirs reste obligatoire ; une base TEST isolée est requise pour toute validation d'écriture.

## Sécurité

Ne pas utiliser les identifiants administrateur dans un script, un fichier ou GitHub ; rotation obligatoire. Les valeurs réglementaires TVA présentes dans les vues ne sont pas revues par ce lot et nécessitent une vérification juridique distincte.
