# ERP Mortier — Correction Stocks (branche `correctif-db-service`)

## Ce qui change

- **Même API Python publique** pour quatre fonctions : `enregistrer_entree_mp`, `enregistrer_sortie_mp`, `enregistrer_entree_pf`, `enregistrer_sortie_pf`. Les retours historiques sont conservés (le coût total de `sortie_mp` reste un `float`). Paramètre optionnel `operation_id` ajouté uniquement en argument nommé.
- **Une seule transaction PostgreSQL par mouvement**, au lieu d'écritures successives `update_hybrid` / `insert_hybrid` pouvant laisser des stocks incohérents.
- Prélèvement FIFO physique, valorisation au **CMP existant** (le FIFO ne valorise pas la sortie au prix historique du lot).
- Contrôle des quantités et coûts (nombres finis, positifs sauf coût nul permis), requêtes RPC privées, sérialisation par article et détection des relances via `operation_id`.
- Deux **tables techniques** additionnelles, `erp_stock_operations` (idempotence) et `erp_stock_outbox` (événements de synchronisation). **Aucune seconde table métier de stocks.**

## Attention — ne pas fusionner avec `main` maintenant

La nouvelle version **ne peut pas fonctionner avant la migration SQL et la configuration de la clé serveur**. Elle est volontairement *fail-closed*, sans mode de secours vers les anciennes écritures non atomiques.

La synchronisation vers **Google Sheets n'est PAS exécutée automatiquement** : un événement est stocké dans `erp_stock_outbox`, mais il faut développer/tester un consommateur idempotent pour alimenter les anciennes feuilles utilisées ailleurs par l'ERP. Tant que cette fonctionnalité n'est pas validée, **ne pas déployer en production**.

La fonction SQL n'a pas été exécutée sur une instance PostgreSQL réelle dans le cadre de cette livraison. Tests Python : simulations seulement. Les tests d'intégration SQL, de concurrence et d'autorisations PostgREST restent obligatoires.

## 1. Appliquer les modifications en local

Dans PowerShell, après avoir téléchargé le fichier `.patch` dans `Downloads` :

```powershell
cd "C:\LH\Perso\ERP_PYT\erp-mortier"
git status
git branch --show-current   # doit afficher correctif-db-service
$patch = Join-Path $env:USERPROFILE "Downloads\correctif_stocks_atomiques.patch"
git apply --check "$patch"
git apply "$patch"
```

Ne forcez pas l'application si `git apply --check` échoue. Un seul dossier de projet est utilisé.

## 2. Vérifier les tests Python AVANT le push

```powershell
.\.venv\Scripts\python.exe -m compileall -q app.py core config modules
.\.venv\Scripts\python.exe -m pytest -q tests/test_stocks_atomic.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_app_security.py tests/test_auth_hardening.py tests/test_db_service_security.py
# Ne lancez pas la suite entière si des tests existants écrivent dans la base de production.
git diff --check
git status
```

Les tests sont isolés et ne sollicitent pas Supabase.

## 3. Préparer un PROJET SUPABASE DE TEST (jamais le projet en production)

1. Vérifier que les tables métier de l'ERP y sont présentes, avec la structure que vous avez communiquée. Charger **uniquement des données de test**.
2. Exécuter `sql/stock_preflight_readonly.sql`. Résoudre et expliquer les incohérences de stock avant la migration. Ne jamais les « corriger » aveuglément.
3. Exécuter `sql/002_atomic_stock_movement.sql` via **SQL Editor**. Surveiller toute erreur PostgreSQL.
4. Exécuter `sql/stock_smoke_test_rollback.sql` **une seule fois** dans le projet de test; le dernier `ROLLBACK` annule les données du test. Si un test échoue, investiguer la transaction et ne pas continuer.
5. Depuis l'API, vérifier que `anon` et `authenticated` ne peuvent pas appeler `public.erp_apply_stock_movement`. Vérifier qu'un client serveur autorisé le peut, et réaliser des essais de concurrence et de répétition d'opérations.

## 4. Clé serveur Streamlit, uniquement sur un ENVIRONNEMENT DE TEST

Dans Streamlit Secrets **de l'application de test seulement** :

```toml
[supabase]
url = "https://votre-projet-test.supabase.co"
key = "votre-cle-existante-test"
stock_service_key = "CLE_SERVICE_ROLE_TEST_GARDEE_SECRET"
```

La clé **service_role** a des droits élevés : ne jamais la placer dans GitHub, dans les tests, dans une capture d'écran, dans le navigateur, ni dans un fichier suivi par Git. Elle n'est pas une permission métier : `check_server_permission()` continue à vérifier le compte applicatif dans Supabase. Le client RPC serveur ne doit jamais être utilisé pour connecter un utilisateur à `auth.sign_in_with_password`.

⚠️ L'application Streamlit lancée localement peut toujours pointer vers la base de PRODUCTION si `.streamlit/secrets.toml` contient l'URL de production. Ne **jamais** tester de mouvements en local sans vérifier les secrets.

## 5. Reprises après coupure réseau

Par défaut, chaque appel produit un identifiant UUID différent. **Pour garantir l'absence de doublon d'un document déjà exécuté, l'appelant doit fournir un identifiant métier stable** :

```python
from modules.stocks.service import enregistrer_sortie_mp

cout = enregistrer_sortie_mp(
    "MP-0001", 50, "OF-2026-0102:ligne-3",
    operation_id="STOCK:SORTIE:OF-2026-0102:ligne-3",
)
```

Ce même `operation_id` doit être réutilisé lors d'une reprise, à quantité, article et référence identiques. En cas de timeout, `StockOperationError.operation_id` est disponible : il faut inspecter l'opération dans `erp_stock_operations` et retenter avec **exactement le même identifiant**, jamais en générer un nouveau.

## 6. Points BLOQUANTS avant de passer en production

- Évaluer toutes les fonctions des modules Achats / Ventes / Production susceptibles de modifier directement `stock_actuel`, `lots` ou `mouvements`. Elles doivent utiliser **exclusivement** la transaction et être accompagnées de tests.
- Le remplacement des écritures hybrides coupe temporairement la mise à jour des feuilles Google Sheets. Le worker de l'outbox reste à développer et à tester.
- Vérifier que les utilisateurs autorisés à recevoir/produire/livrer disposent bien des permissions nécessaires au module `Stocks`. Les rôles modifiés exigent un audit.
- La sortie d'une **seule MP** est atomique, **la clôture d'un OF comprenant plusieurs MP + une entrée PF ne l'est PAS encore**. Il faudra créer une RPC dédiée à la clôture intégrale des OF, avant utilisation en production.
- Contrôler les dates de péremption, lots bloqués, retours et inventaires : ils ne sont pas gérés par ces quatre fonctions.
- Vérifier RLS/GRANT, secret service_role, rapprochement stock/lot, concurrence (deux sessions), restauration de sauvegarde, et stratégie de retour arrière avant le `merge`.

## 7. Git

Lorsque **les tests Python isolés** ont réussi :

```powershell
git add modules/stocks/service.py tests/test_stocks_atomic.py sql/002_atomic_stock_movement.sql sql/stock_preflight_readonly.sql sql/stock_smoke_test_rollback.sql README_STOCK_ATOMIC.md
git diff --cached --check
git diff --cached --stat
git commit -m "Preparer transactions atomiques de stock et tests"
git push origin correctif-db-service
```

Le push sur la branche de correction n'affecte pas Streamlit Cloud si seul `main` est déployé. **Ne pas fusionner la Pull Request avant la validation et l'intégration complète**.
