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


## Correction de régression CI
- Sur commit initial `9ff0c3c`, le workflow `41912435709` a échoué sur deux assertions historiques : huit boutons d'activité Production attendus alors que le bouton historique ajoute une neuvième interaction ; trois erreurs de chargement CRM attendues alors que la consultation sans droits d'écriture et le chargement manuel n'interrogent désormais que Pipeline au rendu initial.
- `tests/test_010A_02D_02_production_activity.py` mis à jour pour neuf callbacks de bouton (commit `781ff42`).
- `tests/test_strict_reads_ui.py` adapté à une seule erreur CRM attendue dans le scénario de permissions restreintes (commit `77d1e79`).
- Ces adaptations documentent les changements fonctionnels volontaires, sans neutraliser les tests des refus ni divulguer les données.
- Vérifier les workflows de `77d1e79` avant de déclarer le lot validé.


## Extension — pagination historique (04/11/2026)
- `core/strict_reads.py` : `fetch_history_page_strict`, bornée à 1–100 lignes/page (défaut 50), pages 1–1000, maximum 100 000 lignes annoncées. Contrôle serveur RBAC à chaque requête, sélection de colonnes autorisées, tri décroissant par clé primaire, `count=exact`, rejet de résultats incomplets/ambigus. Pas de cache ni écriture.
- `modules/crm/service.py` : `get_interactions_page`. `modules/crm/views.py` : page CRM choisie par `number_input`, affichage à la demande des 50 lignes et du total.
- `modules/production/service.py` : `get_consommations_of_page`, `get_controles_qualite_page`. `modules/production/views.py` : numéro de page commun aux deux registres, 50 lignes chacun au maximum ; aucun chargement historique sans clic.
- Les anciennes fonctions d'accès complètes restent intactes pour les autres appels ; changement limité aux vues d'historique.
- Tests `tests/test_history_page_strict.py` et adaptations `tests/test_perf_crm_production_histories.py` : limites, permissions, pages incomplètes, compte exact, compatibilité des vues.
- Commits : `076fd33`, `b0d479b`, `2ac2f68`, `df3640c`, `9a9cd12`, `732694d`, `fc50714`. GitHub Actions lancées ; valider leur conclusion.
- Limitation explicite : pagination par offset, **pas de snapshot PostgreSQL transactionnel**. En cas d'insertions entre consultations, une ligne peut changer de page ; ceci ne remplace pas un journal immuable. Le nombre annoncé reste celui de la requête courante.
- Pas de migration SQL, de changement de fiscalité, d'émission de document ou de modification de données de production.
