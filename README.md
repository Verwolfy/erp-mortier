# ERP Mortier — noyau renforcé (ajout indépendant)

Module Python 3.12 + migrations Supabase PostgreSQL, conçu comme **socle de correction** du calcul de nomenclature et de l'enregistrement transactionnel des réceptions/OF.

**Ce projet N'EST PAS un remplacement validé de l'ERP GitHub existant.** Le dépôt amont n'a pas pu être récupéré depuis cette session. Les tables créées sont séparées; l'application Streamlit actuelle ne les utilise PAS automatiquement.

## Livré

- `erp_engine/formulation.py` : `Decimal`, recettes normalisées, contrôle des unités, conversion uniquement avec densité, erreurs explicites.
- `erp_engine/gateway.py` : accès via RPC Supabase, demande idempotente, validation en entrée, erreurs UI filtrées.
- `sql/001_atomic_manufacturing.sql` : schéma distinct, transactions PostgreSQL, verrous d'articles, lots FIFO, contrôles d'accès multi-société, journaux de mouvements, coûts matières des OF, refus en cas de stock insuffisant.
- `tests/` : tests unitaires Python + mocks de la façade RPC.
- `.github/workflows/` : CI partielle de ce composant.

## Exécution des tests

```bash
cd erp_hardening
python -m pip install 'pytest>=8,<10'
python -m pytest -q
```

## Intégration (NON automatique)

1. Sauvegarder la base; créer un environnement de préproduction.
2. Faire relire la migration et sa compatibilité avec la version Postgres par le DBA.
3. Appliquer `sql/001_atomic_manufacturing.sql` sur **un Supabase de test**, jamais directement en production.
4. Créer les `items`, les `recipes` et `recipe_lines`, puis les valider en `APPROVED`, en utilisant les comptes administrateur SQL seulement. Définir chaque unité d'article dans sa base de gestion (kg, L ou u) ; aucune conversion tacite.
5. Provisionner les lignes `company_members` associées aux vrais UUID de **Supabase Auth**. Les comptes actuellement gérés par bcrypt + Streamlit ne sont pas automatiquement reconnus par `auth.uid()`.
6. Utiliser le client Supabase associé à la session de l'opérateur connecté, jamais une clé `service_role` dans le navigateur ou du code public. Le rôle `admin`, `inventory` ou `production` est contrôlé dans PostgreSQL.
7. Adapter les écrans et les anciennes écritures (`modules/production`, `modules/achats`, `modules/stocks`) pour appeler EXCLUSIVEMENT ces RPC et ne plus écrire dans les anciens stocks en parallèle. Prévoir une migration de données des stocks et des lots : ne pas les dupliquer.
8. Exécuter des **tests d'intégration sur Supabase réel** pour concurrence, unicité des lots, échec transactionnel, droits SQL/RLS et entrées/sorties comptables; comparer aux valeurs historiques avant le basculement.
9. Google Sheets ne doit plus être une seconde source transactionnelle : exporter par outbox ou synchronisation différée, avec retry et détection de conflit. Ce flux n'est pas fourni ici.

## Fonctionnement

La quantité d'un composant est : `quantité recette / quantité de référence * quantité de produit fini`. Exemple : 300 kg pour une recette de 1 000 kg et un OF de 500 kg donnent 150 kg, pas 150 000 kg.

Les réceptions et les OF enregistrent une opération unique par `(company_id, operation_id)` : utiliser la **même clé UUID** lors d'une relance réseau; ne jamais générer un nouvel UUID pour la reprise de la même opération. Une clé réutilisée avec d'autres paramètres est refusée.

## Limites importantes

- Aucun déploiement, clone du dépôt d'origine, tests PostgreSQL réels, benchmark, ni fusion GitHub n'ont été effectués.
- Les workflows achats/ventes, facturation, comptabilité partie double, paie, CRM, tableaux de bord, et les migrations de l'ancien schéma restent à traiter.
- Pas de gestion de rebuts, frais indirects, retraitements, packaging détaillé, conversions d'unités en base, ordres de fabrication versionnés ou réservations de stock.
- Les recettes validées doivent être figées fonctionnellement par l'administration; ici l'accès SQL d'administration peut encore les modifier. Ajouter versioning/immutable & approbation qualité avant la production réelle.
- Le mouvement de stock étant un événement de gestion, toute annulation doit enregistrer un mouvement inverse documenté, non effacer l'historique.
- Les coûts de production sont **matières uniquement**; pas des coûts de revient industriels complets.
- Dans le cas d'un utilisateur qui gère ses propres comptes hors Supabase Auth, cette migration ne fonctionnera volontairement pas tant que l'authentification n'est pas adaptée.
- `SQL` n'a pas été testé par un serveur PostgreSQL, sa validité fonctionnelle reste à qualifier.
