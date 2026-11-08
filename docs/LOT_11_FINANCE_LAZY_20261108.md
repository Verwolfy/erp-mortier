# LOT-11 — Finance : lecture ciblée des 11 vues

Date : 2026-11-08. Branche : `perf/lot11-finance-lazy-20261108`.

## Problème

La page `modules/finance/views.py` rendait 11 onglets `st.tabs` à chaque ouverture. Chaque rendu téléchargeait les tables `comptes` et `reglements`, puis exécutait le contenu de tous les onglets (journal, rapprochements, pré-audits, etc.) même s'ils étaient invisibles. Ceci augmentait le nombre de lectures et le risque d'erreur auxiliaire bloquant un autre écran.

## Modification

Navigation `Vue Finance` (11 choix) après la vérification fraîche `_finance_access()` sur le compte serveur. Le contenu d'un seul panneau est rendu, et les deux listes principales sont chargées uniquement lorsque nécessaires :

| Vue | Tables chargées avant traitement propre à la vue |
|---|---|
| Tableau de bord | `reglements` |
| Comptes | `comptes` |
| Règlements | `comptes` |
| Lettrage | `reglements` |
| Journal | `ecritures_comptables` |
| Balance SCF | aucune (lecture au clic uniquement) |
| Rapprochement quittances | aucune (lecture au clic uniquement) |
| Accusés internes | `reglements` |
| Pré-audit Finance → SCF | `comptes`, `reglements` |
| Préparation TVA/SCF | aucune (lecture au clic uniquement) |
| Correspondances Finance/SCF | `comptes` |

Le chargement est borné par `_load_table` et continue de rejeter toute erreur de lecture. Aucune donnée partielle n'est interprétée comme zéro. Les contrôles RBAC de chaque opération, les RPC de trésorerie, les `operation_id`, la reprise après délai et les contrôles de rapprochement restent en place.

## Tests

- `tests/test_lot11_finance_lazy.py` : 11 vues exclusives, absence de lectures hors panneau, autorisation refusée, lecture seule, erreur de source refusée, callback d'activité.
- Contrats historiques `tests/test_finance_views_security.py` mis à jour : lire explicitement Tableau de bord, Comptes, Journal et Pré-audit afin de confirmer les paginations autorisées sans présupposer `st.tabs`.
- `tests/test_010A_02D_02_finance_activity.py` compte le sélecteur ajouté.
- Deux workflows GitHub complets sur la PR, vérification post-fusion sur le HEAD `main`.

## Gains et limites

Évite deux lectures complètes à l'ouverture des six vues diagnostiques qui n'ont pas besoin de toutes ces données. Le nombre exact d'appels dépend de l'action et de la vue active : **aucun gain en ms n'est certifié** sans mesure dans Streamlit authentifié via OPT-04.

Aucune migration, aucun changement de données ou permissions Supabase, aucun changement des taux fiscaux/SCF, aucune homologation comptable introduite. `DB-UNI-01` gelé et environnement TEST inactif. Aucun test d'écriture sur la base de production.

## Suite

LOT-12 RH : rendre une seule des cinq vues (y compris Paie) et charger employés/congés uniquement quand nécessaires ; préserver la séparation `RH` / `Paie` et tous les avertissements « simulation ». Vérifier la version Streamlit authentifiée et renouveler le mot de passe administrateur.
