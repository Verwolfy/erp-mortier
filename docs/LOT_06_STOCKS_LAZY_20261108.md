# LOT-06 — Stocks : rendre uniquement le panneau consulté

**Date :** 2026-11-08. **Branche :** `perf/lot06-stocks-lazy-20261108`.

## Constat de départ

Dans `modules/stocks/views.py`, le widget `st.tabs` provoquait l'exécution des trois vues à chaque rendu, indépendamment de celle consultée. La page chargeait les MP actives avant toute vue, puis les stocks MP, les stocks PF et les catalogues SKU/Produits alors qu'une simple consultation des historiques ou une saisie d'entrée manuelle n'en avait pas besoin.

## Changement Lot-06A

- Remplacement des trois onglets principaux par le sélecteur `Vue Stocks`, conservant exactement les trois écrans existants.
- Le rôle actif est vérifié **depuis Supabase avant d'afficher le sélecteur**.
- `get_mp_actives` n'est appelé pour l'état des stocks et la saisie habilitée que lorsqu'ils sont sélectionnés ; en lecture seule sur la saisie, aucun catalogue n'est chargé.
- Les historiques ne lisent pas les référentiels avant le clic explicite `Afficher les mouvements de stock`. Après le clic, la classification Vrac/Emballages est conservée.
- Les flux d'entrée, identifiants `operation_id`, protections anti-doublon, traitements incertains/confirmés, appels RPC et validations sont laissés inchangés.
- Les sous-onglets Vrac/Emballages/PF du panneau État des stocks restent inchangés pour ce lot ; leur rendu paresseux éventuel fera l'objet d'un second lot indépendant.

## Mesure exacte

| Cas | Lectures supprimées sur le rendu non concerné |
|---|---|
| Historique ouvert sans cliquer Charger | Lecture MP actifs + MP/PF stock + SKU/Produits |
| Saisie manuelle sélectionnée | Lecture des stocks MP/PF + SKU/Produits |
| Saisie affichée sans droit d'écriture | Lecture MP actifs, ainsi que les stocks |
| État des stocks sélectionné | Historique/formulaire non exécutés |

Ces gains sont **des appels Python métier évités** et non des chronométrages réels. Le droit utilisateur est toujours vérifié côté serveur à l'ouverture de la page.

## Vérification et limites

- Six nouveaux tests unitaires hors réseau (navigations exclusives, droits refusés, lecture seule, callback activité, historique sans chargement).
- Adaptation des anciens tests d'entrées et d'historique au comportement de sélection explicite, sans réduire les garde-fous métier.
- GitHub CI complète sur la PR puis sur `main`, uniquement après validation.
- Les sous-vues État des stocks restent toutes calculées quand l'état est sélectionné. Optimiser leur affichage séparément évite de mélanger plusieurs modifications d'interface en une seule PR.
- Aucun SQL, migration, GRANT/RLS, donnée Supabase ni mot de passe modifiés.

## Suite des lots

LOT-06B : sous-vues Stocks Vrac/Emballages/PF à la demande.  
LOT-07 : vues Achats (Commande/Réception/Historique) à la demande.  
LOT-08 : Production (Recette/OF/Suivi/Historiques/Coûts) après revue des tests E2E de clôture.

Blocages transversaux inchangés : authentification Streamlit Cloud et commit réellement déployé non vérifiés, Supabase TEST inactive, rotation du mot de passe administrateur à effectuer. Le hotfix de provenance #60 est sur `main` mais son comportement après connexion reste à confirmer.
