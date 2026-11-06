# Lot 043 — Rapports de coûts industriels sans troncature
Date : 2026-11-06

## Résultat : CI verte sur `main`
- Branche GitHub : `Verwolfy/erp-mortier/main`.
- Commit testé : `3ed8bd03f8f9d3ed1469752cfb53c6686f9bbc52`.
- ERP Python : **2 593 tests réussis, 7 ignorés, 0 échec, 133 warnings**.
- [Suite ERP](https://github.com/Verwolfy/erp-mortier/actions/runs/42207433772) : SUCCESS.
- [Audit de réconciliation](https://github.com/Verwolfy/erp-mortier/actions/runs/42207433796) : SUCCESS.
- Supabase TEST `ffuhbmcfyexsbjwhryvj` : état **INACTIVE** vérifié.
- Aucune migration SQL et aucune modification de données de production dans ce lot.

## Risque traité
Le service `modules/production/cost_service.py` chargeait les pools, assiettes, allocations, synthèses, preuves SCF et instantanés avec des `.limit(500)`, `.limit(1000)` et `.limit(2000)`. En forte volumétrie, l'application pouvait afficher un rapport incomplet sans indication.

## Correctifs appliqués
- `_fetch_all(query, order_by, page_size=500)` itère par pages PostgREST avec `.range(start,end)` et ordre explicite. Supabase renvoie au plus 500 lignes par page.
- Les périodes sont triées de la plus récente à la plus ancienne et listées intégralement; les natures sont également paginées.
- Clés ordonnées par jeu de données : `pool_id` pour les charges et preuves, `of_id,base_imputation` pour assiettes, `pool_id,of_id` pour allocations, `of_id` pour synthèses et dérives.
- Ajout de `pool_id` au SELECT des allocations pour une pagination stable (identifiant de pool + OF).
- Si le volume atteint la limite de sûreté de 100 000 lignes pour un jeu de données ou qu'une requête échoue, le rapport est refusé avec une erreur. Pas de troncature silencieuse ni de dictionnaire de rapport partiel.
- `modules/production/cost_views.py` quitte l'écran avant les formulaires d'écriture si le rapport sélectionné échoue à charger.

## Tests
Fichier `tests/test_industrial_cost_pagination.py` :
- 1 301 enregistrements récupérés sur 3 pages, tri garanti.
- Exactly 1 000 enregistrements -> requête de terminaison supplémentaire.
- Liste vide / tailles de page incorrectes / ordre obligatoire.
- Limite de sécurité -> erreur explicite.
- 1 101 périodes avec tri chronologique décroissant.
- Récupération intégrale de 1 101 charges, 1 203 assiettes, 1 307 allocations, 1 023 synthèses, 1 101 rapprochements SCF et 1 150 dérives.
- Erreur réseau en page 2 -> refus du rapport complet avant même l'audit.
Test `test_incomplete_report_blocks_all_write_forms` : profil habilité sans page complète -> aucun formulaire d'écriture.
Tous les tests sont exécutés en CI GitHub, sur bases simulées : pas de coût ni OF fictifs injectés dans la production.

## Limites restantes
- **La pagination HTTP par offsets ne constitue pas une photographie transactionnelle cohérente** : si des écritures concurrentes modifient l'ordre / le nombre de lignes entre deux pages, la lecture peut varier. Le service garantit la récupération par pages en état stable, pas un snapshot inter-requêtes. Pour des exports réglementaires, préférer des instantanés SQL transactionnels.
- La limite de sûreté de 100 000 lignes est volontaire; au-delà, ajouter un export dédié et une revue de volumétrie plutôt que retourner des chiffres incomplets.
- Les 7 tests ignorés et 133 warnings du dépôt restent à examiner séparément.
- Aucun test navigateur authentifié réel avec utilisateurs Production+Finance et accès limité n'a été effectué.

## Prochaine étape recommandée
1. Identifier si les rapports volumineux sont destinés à un audit officiel; si oui, concevoir un export SQL sous transaction `REPEATABLE READ` avec pagination stable ou snapshot serveur.
2. Contrôler avec une vraie session Streamlit les droits et l'interface de reprise des rapports.
3. Surveiller performance et consommation mémoire des jeux de données très volumineux; ne pas charger simultanément 100 000 lignes de six tableaux sans pagination de présentation.
