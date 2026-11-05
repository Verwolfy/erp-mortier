# Sofiane ERP — Reprise recherche référentiels (05/11/2026)

## Contexte
- Dépôt GitHub `Verwolfy/erp-mortier`, `main`, Streamlit https://nextgent-erp.streamlit.app/.
- Supabase production `wenydirqtmkywbxbxfal`, aucune mutation. Projet test `ffuhbmcfyexsbjwhryvj` conservé inactif.
- Dernier lot validé avant intervention : pagination + filtres de période Stocks/Achats/Ventes, commit `c0943fd`, CI tests `42006808434` et audit `42006808502` réussis.

## Changements
- `modules/admin/catalog_search.py` : service de recherche read-only pour `clients`, `fournisseurs`, `produits`, champs autorisés `nom` ou identifiant. Validation des champs/termes (2 à 80 caractères, pas de caractères génériques SQL), page 1 à 1000, 50 lignes maximum, count exact, vérification des clés uniques et contrôle serveur RBAC avant requête. Projection minimale `id,nom,categorie,actif` : pas de NIF, RC, téléphone ni email affiché. Ne pas divulguer les erreurs SQL.
- `modules/admin/catalog_search_view.py` : petit formulaire d'identifiant/nom et page ; exécution seulement après clic, affichage de synthèse et résultats.
- `modules/admin/views.py` : recherche ajoutée aux onglets Clients, Fournisseurs et Produits. Les éditeurs complets existants restent accessibles après case `Afficher / modifier le référentiel ...`, sans chargement global initial. Les méthodes d'écriture métier et garde-fous restent inchangés.
- `tests/test_admin_catalog_search.py` : droits, validation, projections confidentielles, exactitude de page, erreurs de résultats et disponibilité des éditeurs.
- Commits du lot : `a6774f7`, `bbb7688`, `831a99c`, `e1e6995`.

## Limites et suite
1. Vérifier verdict final de GitHub Actions des derniers commits et corriger toutes régressions.
2. Tester visuellement Administration > Clients/Fournisseurs/Produits, avec droits lecture seule et édition, puis constater le gain réseau. Les actions de recherche ne modifient pas la base.
3. Sur très gros catalogues, une recherche ILIKE préfixée par % peut rester coûteuse sans index adapté. Examiner un plan `EXPLAIN` en lecture seule avant toute proposition d'index (modification DB à valider).
4. Les autres écrans éditables référentiels sont inchangés ; ne pas confondre recherche rapide et filtrage sûr des écritures.
5. Les taxes et le registre QR SQL 033 restent hors du présent lot ; migration QR NON appliquée, brouillons NON émis.
6. La recherche de données de tiers ne doit être disponible qu'aux rôles déjà autorisés. Aucun contournement RLS, aucune copie publique de données.

## Règles de reprise
Exécuter automatiquement les corrections non critiques, vérifier CI, ne pas inventer de valeurs juridiques/comptables. Résumé concis en français : résultat précédent ; prochaine action, pourquoi/comment ; ce que l'utilisateur doit faire.
