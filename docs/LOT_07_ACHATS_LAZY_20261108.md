# LOT-07 — Achats : vues chargées à la demande

**Date :** 2026-11-08. **Branche :** `perf/lot07-achats-lazy-20261108`.

## Constat et changement

Les trois onglets Streamlit `Nouvelle Commande`, `Réception & Entrée Stock` et `Historique & Suivi` étaient exécutés à chaque affichage. Même sur une simple consultation d'historique, le module pouvait charger fournisseurs, matières premières, commandes réceptionnables et formulaires associés.

- Un sélecteur `Vue Achats` affiche **une seule vue à la fois** ; l'accès au compte et les permissions serveur restent évalués avant toute navigation.
- Le formulaire de commande continue de charger fournisseurs, matières premières, devises, modes et délais de paiement **seulement** lorsqu'il est sélectionné.
- Le panneau Réception continue de valider les commandes, soldes de lignes, devises, taux et états de réception **seulement** lorsqu'il est sélectionné.
- L'Historique reste paginé au serveur et sans chargement avant clic ; seuls les écrans historiques explicitement consultés affichent les contrôles de pagination.
- `read_section` enveloppe toujours séparément chaque vue ; les erreurs d'autorisation/lecture restent refusées.
- Pas d'écriture ou de RPC modifiés, pas de contournement de contrôle, pas de modification d'idempotence `operation_id` ni de gestion d'opérations `uncertain/confirmed`.

## Gain vérifiable

L'affichage de l'Historique sans clic sur Charger n'exécute **aucune lecture du catalogue ni du registre des commandes réceptionnables**. Le panneau Réception n'exécute pas le formulaire Nouvelle Commande, et inversement. Il s'agit d'évitements d'appels, **pas** d'une mesure de latence réseau ou de performances en ms.

## Critères de validation

- 6 tests nouveaux de lecture ciblée, refus RBAC, lecture seule, non-exécution des vues inactives et callback activité.
- Contrats historiques UI de réception, anti-doublon et droits maintenus, avec sélection explicite de la vue pour les assertions antérieures sur `st.tabs`.
- Deux workflows complets GitHub Actions puis vérification du commit `main` après fusion.
- Aucun changement SQL, migration, accès Supabase, compte ou secret.

## Étapes suivantes

LOT-06B : sous-vues MP/Emballages/PF des Stocks en mode à la demande.  
LOT-08 : Production, après revue de ses formulaires de recettes, ordres de fabrication et clôtures.  
Ne pas considérer l'état du déploiement Streamlit Cloud confirmé tant qu'une recette authentifiée n'a pas eu lieu. Supabase TEST inactive, tests E2E et renouvellement du mot de passe administrateur restent prioritaires.
