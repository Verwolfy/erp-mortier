# Reprise NEXTGEN ERP — Optimisation CRM et Production — 04/11/2026

## Résultat
- Dépôt : `Verwolfy/erp-mortier`, branche `main` ; ERP : https://nextgent-erp.streamlit.app/
- Lot précédent Tableaux de bord : tests GitHub Actions `41911751193` et audit `41911751274` réussis sur `7aa7469`.
- CRM : `modules/crm/views.py` ne charge l'historique des interactions qu'après clic sur **Afficher l'historique CRM**. Le catalogue Clients n'est plus chargé en mode CRM sans droit d'écriture. Lecteur strict et permissions conservés.
- Production : `modules/production/views.py` ne charge consommations OF et contrôles qualité historiques qu'après clic sur **Afficher l'historique Production**. En consultation seule, aucun chargement des référentiels Produits, Matières premières et SKU requis pour les formulaires de création ; le suivi des OF demeure accessible. `_production_access` reste le garde d'accès.
- Tests statiques ajoutés dans `tests/test_perf_crm_production_histories.py`, avec contrôle de la condition de lecture, du panneau et des permissions.
- Commits : `4107512`, `1d26576`, `ccf6ae7`, `484109e`, `cd74d52`, `5049687`.
- Aucun mouvement de stock, création de document, changement fiscal ni écriture Supabase. QR SQL 033 toujours non déployé.

## Reste à contrôler
1. Vérifier CI GitHub Actions tests ERP et audit de réconciliation du dernier commit ; corriger en cas d'échec.
2. Vérification fonctionnelle dans Streamlit : ouvrir CRM > Historique des échanges et Production > Consommations et contrôles ; cliquer sur les boutons, tester un profil lecture seule. L'historique n'est plus affiché automatiquement : clic nécessaire.
3. Mesurer la latence réelle et le nombre de lectures avec traces techniques sans secrets ni données personnelles.
4. Étudier la pagination des gros historiques CRM/Production plutôt que de récupérer systématiquement toutes les lignes après clic.
5. Conserver les contraintes RBAC, l'absence de cache inter-utilisateur, l'absence d'émission fiscale et la migration QR préparatoire non appliquée.

## Contextes techniques
- GitHub `Verwolfy/erp-mortier` branche `main`; production Supabase `wenydirqtmkywbxbxfal` non modifiée.
- Base TEST `ffuhbmcfyexsbjwhryvj` demeure en pause.
- Les contrôles d'audit transversaux Stocks, Ventes, Achats, Finance, RH sont disponibles via Administration > Qualité référentiels.
