# Lot 044 — Cohérence de la pagination analytique

Date : 2026-11-06.

## Résultat vérifié
GitHub `Verwolfy/erp-mortier`, branche `main`. Correctif publié et testé au commit `0d4fa7227bafc964ce4529b7e3712738cbf4b88f`.

- Tests ERP : **2 598 réussis, 7 ignorés, 0 échec, 133 avertissements**. [GitHub Actions — tests](https://github.com/Verwolfy/erp-mortier/actions/runs/42213482500), statut success.
- Audit de réconciliation : [GitHub Actions — audit](https://github.com/Verwolfy/erp-mortier/actions/runs/42213482448), statut success.
- Supabase TEST `ffuhbmcfyexsbjwhryvj` : `INACTIVE` au début du lot.
- **Aucune migration SQL, aucune modification des données TEST ou PROD** dans ce lot.

## Risque identifié
Après le lot 043, le service Python récupérait six jeux de données par pages PostgREST ordonnées, mais n'explicitait pas un refus lorsqu'une modification concurrente entraînait des clés dupliquées / pages désordonnées. Une page SQL dont `data` était `None` était interprétée comme une liste vide.

## Correctifs
Dans `modules/production/cost_service.py` / `_fetch_all` :
1. Refus de `response.data is None`.
2. Refus de toute clé de tri absente dans une ligne.
3. Vérification monotone stricte des clés ordonnées, y compris entre les pages, pour signaler un doublon ou une désorganisation de l'ordre.
4. Conservation de la pagination de 500 lignes, de la limite de 100 000 par jeu et du refus de résultat incomplet.
5. Les formulaires Streamlit restent bloqués quand `get_period_report` échoue (règle du lot 043).

Dans `tests/test_industrial_cost_pagination.py` :
- Cas de doublon à la frontière de pages, clé absente, `data=None`, deuxième page désordonnée et rapport intégral interrompu avant appel d'audit.
- Fixtures volumétriques mises à jour pour inclure les véritables clés de tri composites : `of_id + base_imputation` pour les assiettes, `pool_id + of_id` pour les allocations.

## Déroulement CI
Une exécution intermédiaire a échoué car une fixture ancienne omettait la colonne `base_imputation` pour le tri composite. Cette fixture a été corrigée au commit `0d4fa7227bafc964ce4529b7e3712738cbf4b88f` ; la suite et l'audit finaux sont tous deux réussis. Aucun changement SQL ni comptable.

## Limites et suites
- Un tri strict détecte les doublons et certains déplacements causés par les écritures concurrentes, mais **ne garantit pas un snapshot cohérent entre requêtes HTTP**. Une suppression qui saute une clé sans créer de doublon reste possible.
- Pour un audit financier officiel, envisager un export transactionnel serveur sous isolation appropriée ; ne pas décrire les rapports paginés comme certifiés.
- L'interface de rendu charge encore plusieurs tableaux en mémoire. Une présentation paresseuse par section peut améliorer les performances.
- Un test navigateur Streamlit avec une vraie session Production+Finance et un profil limité reste à réaliser (mocks et tests SQL ne couvrent pas l'authentification de bout en bout).
