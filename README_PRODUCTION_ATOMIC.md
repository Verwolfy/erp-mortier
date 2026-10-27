# ERP Mortier — Itération Production, fermeture atomique des OF

**Statut : ITERATING / jamais prêt pour la production sans tests SQL réels.**

## Principales corrections

- Le contrôle qualité positif **n'appelle plus** les fonctions Python de sortie MP / entrée PF successivement. Une seule RPC Postgres `erp_close_manufacturing_order` prend en charge l'OF complet dans **une transaction**.
- La RPC utilise l'autre RPC existante `erp_apply_stock_movement` pour le FIFO, les lots et le CMP ; tous ces appels imbriqués sont annulés si une étape échoue.
- Les `consommations_of` sont écrites **par lot réel consommé**, depuis `lot_allocations` : aucun identifiant inventé `FIFO-OF...`.
- Une table technique `erp_of_closures` stocke la demande et le résultat d'un OF : une relance identique retourne le résultat initial, une relance différente est rejetée. `erp_of_outbox` est créée pour la synchronisation différée, **sans worker fourni**.
- Un compte ERP doit avoir la permission **Production** et, pour une clôture conforme, les permissions d'écriture **Stocks**. La RPC elle-même n'est accordée qu'à `service_role` côté serveur ; pas d'appel direct par un navigateur.
- `changer_statut_of()` appelle maintenant `erp_start_manufacturing_order`, qui autorise uniquement `PLANIFIE → EN_COURS` sous verrou PostgreSQL (ou un rappel idempotent). Les clôtures `TERMINE` / `REJETE` restent réservées à la RPC atomique.
- Les fonctions de recherche filtrées utilisent `fetch_data_filtered` côté Supabase pour éviter de charger toute la table.
- Les fonctions de création de recette / OF vérifient les retours des insertions, mais **la création de recette et de ses lignes reste non atomique** : c'est une faiblesse pour une prochaine itération.

## Formulations : hypothèse conservée, à confirmer avec le métier

Le champ **`lignes_recette.quantite_par_unite`** implique la quantité de MP par une unité produite. Le service d'origine utilisait :

`besoin_MP = quantite_par_unite * quantite_produite`

La SQL conserve **exactement** cette convention, sans utiliser arbitrairement `recettes.rendement_unite` comme facteur. **Si la recette est en réalité renseignée pour un lot de 1 000 kg, ce calcul serait faux et la production doit rester bloquée tant que la convention réelle n'est pas déterminée.** Vérifier manuellement les unités de MP, l'unité de production du produit, et les conversions des SKU (`facteur_conversion`, `poids_net`). Rien n'effectue une conversion kg ↔ L ni pièces ↔ kg.

## Installation sur la branche Git locale

Prérequis : ne pas avoir de modifications en attente ; branche `correctif-db-service`.

```powershell
cd "C:\LH\Perso\ERP_PYT\erp-mortier"
git status
$patch = Join-Path $env:USERPROFILE "Downloads\correctif_production_atomique.patch"
Test-Path $patch
git apply --check "$patch"
git apply "$patch"

.\.venv\Scripts\python.exe -m compileall -q app.py core config modules
.\.venv\Scripts\python.exe -m pytest -q tests/test_production_atomic.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_app_security.py tests/test_auth_hardening.py tests/test_db_service_security.py tests/test_stocks_atomic.py tests/test_production_atomic.py
git diff --check
git status
```

**Ne PAS exécuter ces tests généraux sur une base de production.** Les cinq fichiers de tests listés ci-dessus utilisent des simulations, mais d'autres tests éventuels du projet peuvent écrire dans la vraie base.

## Supabase : tests uniquement sur projet distinct

1. Créer un projet Supabase de **TEST**, charger le schéma et des **données synthétiques** dans les cinq tables métiers (`ordres_fabrication`, `recettes`, `lignes_recette`, `consommations_of`, `controle_qualite`) ainsi que les tables de Stocks existantes.
2. Vérifier le SQL préalable `sql/002_atomic_stock_movement.sql` sur ce projet. **La migration 003 nécessite cette fonction.**
3. Exécuter les diagnostics `sql/production_preflight_readonly.sql` et vérifier manuellement la convention des recettes / unités. Corriger les incohérences dans des données de TEST seulement.
4. Appliquer `sql/003_atomic_manufacturing_close.sql` (elle crée les RPC de démarrage et de clôture) via SQL Editor **sur le projet de TEST uniquement**. Arrêter immédiatement en cas d'erreur ; aucune validation PostgreSQL réelle n'a encore été faite.
5. Dans Streamlit de **TEST**, la clé privée `[supabase].stock_service_key` doit déjà être configurée côté serveur. Ne jamais exposer cette clé dans Git, navigateur ou capture.
6. Tester séparément : conformité OUI, NON, insuffisance sur la 2e matière, lot expiré/bloqué, deux OF concurrents sur les mêmes MP, répétition identique après timeout, répétition différente, panne avant entrée PF. Vérifier qu'il n'y a **aucune écriture partielle** après erreur.
7. Examiner `erp_stock_outbox` **et** `erp_of_outbox`. Un système de synchronisation idempotent vers Google Sheets reste à développer. Ne pas fusionner avant son test et la validation des autres modules.

## Contrôles bloquants avant déploiement

- **Droits** : la clé serveur de Stocks a des privilèges élevés, doit rester côté Streamlit et être strictement réservée aux RPC attendues ; contrôle des permissions dans les services et audit des `GRANT` / RLS.
- **Schéma** : tests Postgres + PostgREST réels, concurrence et intégrité des lots, validation des mouvements de ventes et achats. Une écriture extérieure aux RPC atomiques peut invalider la sérialisation.
- **Traçabilité et CQ** : OF terminé une fois, rejets non consommateurs, véritables lot_id, reprise après timeout avec paramètres identiques.
- **Performance** : les lectures de tableaux complets `get_recettes()` et `get_ordres_fabrication()` sont encore non paginées ; optimiser avec un plan de migration ultérieur.
- **Recettes** : elles peuvent être modifiées en parallèle des clôtures ; aucune immutabilité complète des recettes approuvées n'est établie. La création de recette + lignes reste non atomique.
- **Conversion de quantités** : unité de production, conditionnement et formule de batch doivent être confirmés ; **n'automatisez pas une conversion non prouvée**.
- **Synchronisation Sheets** : le travailleur des outbox manque. Si une interface lit encore Sheets, elle restera en retard.
- **Couts** : FIFO physique + CMP financier (valeur retournée par la RPC stock) conservés. Pas de valorisation des lots par leur coût propre.

## Git : commit et push, pas de mise en production

Après tests locaux réussis :

```powershell
git add modules/production/service.py tests/test_production_atomic.py sql/003_atomic_manufacturing_close.sql sql/production_preflight_readonly.sql README_PRODUCTION_ATOMIC.md
git diff --cached --check
git diff --cached --stat
git commit -m "Preparer cloture atomique des OF et tracabilite"
git push origin correctif-db-service
```

Le push sur cette branche **ne fusionne pas avec `main`**. Si GitHub Actions exécute des tests sur toutes les branches, vérifiez-les. Ne jamais fusionner sans essais de bout en bout sur l'environnement de test.
