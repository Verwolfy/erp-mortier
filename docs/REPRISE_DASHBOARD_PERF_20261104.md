# Reprise Dashboard — 2026-11-04

Branche main. Commit 9a58a4a : lecture des tables mutualisée pendant un seul rendu de Dashboard par ContextVar et context manager. Aucune donnée persistée, aucune écriture Supabase. Toute section reçoit un DataFrame distinct. Les erreurs de première lecture restent propagées.

CI du commit : tests ERP 41910974346 réussis ; audit 41910974307 réussi.

À faire : ajouter un test pytest qui garantit une seule lecture dans le scope, réinitialisation après le scope, et non-caching des erreurs. Une tentative de publication de tests/test_dashboards_read_scope.py a été bloquée ; blob 03a6fc69d17cde4a4afe15cc3ae377cde3f4595c non intégré à main. Vérifier l'affichage Streamlit sur session habilitée et mesurer latence/réduction des appels réseau. Continuer les optimisations Achats/Ventes/Finance en respectant RBAC et sans modifier fiscalité. Registre QR 033 non déployé.


## Mise à jour : optimisation lectures ciblées
- `tests/test_dashboards_read_scope.py` est désormais réellement publié et versionné dans `main` (commit `2f32dc8`), puis étendu pour vérifier refus RBAC non cachés et scopes imbriqués (commit `51047a6`).
- `modules/dashboards/service.py` (commit `bfb1e6a`) : évite de lire `lignes_facture` et `stock_actuel_pf` pour le P&L si aucune facture client validée ne figure dans la période ; charges fournisseurs/paie restent consultées. Évite `lignes_achats` si la période d'achats est vide, tout en conservant la détection globale des commandes en retard.
- `tests/test_dashboards_read_scope.py` : nouveaux tests de non-lecture sur périodes vides (commit `c61bc3b`). Aucun calcul fiscal ou solde de production modifié.
- Vérifier le verdict GitHub Actions du dernier commit et les tests Streamlit connectés. Aucun gain de latence réel mesuré à ce stade.
