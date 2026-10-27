# Achats et réceptions — correctif transactionnel (TEST uniquement)

**Statut : ITERATING. Ne PAS fusionner avec `main`. Les migrations SQL n'ont pas été exécutées contre un vrai PostgreSQL dans cet environnement.**

## Ce que le correctif change

- `create_commande_achat()` réalise un seul appel `erp_create_purchase_order` : commande et lignes sont insérées dans une transaction. Les champs métiers/identifiants restent dans les tables existantes.
- `creer_bon_reception()` réalise un seul appel `erp_receive_purchase_order` : verrouillage de la commande, validation des quantités déjà reçues, mouvements de stock et lots via `erp_apply_stock_movement`, lignes BR, puis statut de commande, le tout atomiquement.
- Une réception partielle passe la commande en `PARTIELLEMENT_RECEPTIONNE`. La vue Achats et ses listes de statut **doivent impérativement être auditées et adaptées** avant tout déploiement.
- Les lignes de réception enregistrent le **vrai** `lot_id` retourné par la RPC stock, plus de référence fictive `BR-...`.
- Plusieurs lignes d'une réception correspondant à la même MP sont regroupées par MP en SQL (quantité totale, coût d'entrée moyen pondéré), avec **un seul lot et une seule ligne BR par MP**. Vérifier que cette agrégation correspond au besoin métier, surtout pour des lots fournisseur distincts.
- Un BR avec `controle_conformite` différent de `OUI` est refusé ; les réceptions non conformes demandent un circuit de quarantaine distinct.
- Un identifiant d'opération (`operation_id`) peut être fourni pour éviter les doubles créations après un timeout. **L'interface doit conserver cet identifiant pendant toute tentative / reprise**. Si aucun identifiant n'est fourni, un nouvel UUID est créé ; deux clics avec deux UUID restent deux opérations indépendantes.
- Les opérations donnent un `PurchaseOperationError` avec `.operation_id` si le résultat est incertain : **ne jamais relancer avec un nouvel identifiant sans réconciliation**.
- Le SQL crée uniquement les tables techniques `erp_purchase_operations` et `erp_purchase_outbox`, pas de doublon de tables métier. L'outbox et celle de Stocks **n'ont pas de worker de synchronisation Google Sheets** à ce stade.

## Préparation obligatoire

1. Garder la branche `correctif-db-service` ; ne pas exécuter cette migration sur Supabase de production.
2. Créer une base Supabase de **TEST distincte**, avec données synthétiques, et y appliquer `sql/002_atomic_stock_movement.sql` en premier.
3. Exécuter `sql/achat_preflight_readonly.sql` ; examiner les commandes sans lignes, BR sur-réceptionnés et références de lots manquantes.
4. Vérifier que les colonnes et PK du schéma correspondent exactement aux SQL et que les écritures Stocks hors RPC sont désactivées.
5. Appliquer `sql/004_atomic_purchases.sql` **uniquement sur TEST** et contrôler les permissions `service_role`, les comptes utilisateurs, l'absence d'accès aux RPC depuis `anon` / `authenticated`.
6. Tester une commande, une réception partielle puis totale, réception concurrente, rupture réseau après commit, même operation_id après timeout, quantité excessive, MP absente de commande, cas d'échec sur la 2e matière (aucun lot ni BR partiel).
7. Adapter `modules/achats/views.py` et tout appel aux statuts, puis tester les utilisateurs Achats (écriture) et Stocks (écriture), ainsi qu'un lecteur seul.
8. Mettre en place et tester un worker idempotent de synchronisation de `erp_purchase_outbox` et `erp_stock_outbox` avant la fusion, si Google Sheets doit rester une copie à jour.
9. Vérifier l'unité des quantités commandées vs livrées (`qte_cond`, `qte_totale`), les prix en devise et le taux de change. **Aucune conversion implicite d'unité n'est ajoutée.**

## Limitations et points de conception

- Les documents restent numérotés par `generate_unique_id()` à partir de la liste actuelle des documents ; ceci n'est pas un compteur transactionnel résistant à plusieurs créations simultanées. Le SQL rejette les collisions mais **n'invente pas de nouvelle numérotation**. Un compteur PostgreSQL transactionnel reste à concevoir.
- Les champs de dates sont du texte dans le schéma communiqué ; le SQL ne transforme pas leur type.
- Le total de ligne est conservé tel qu'il est saisi par l'UI, car `prix_unitaire` peut être exprimé par conditionnement et non par unité de stock. Validation métier des prix et conversion à préciser.
- Le prix unitaire d'une réception est autorisé à zéro pour conserver le comportement actuel ; la validation financière des réceptions gratuites doit être revue.
- `fetch_data()` est susceptible de renvoyer une liste vide sur une erreur réseau, ce qui peut provoquer un identifiant documentaire déjà utilisé ; l'insertion SQL refusera la collision mais n'empêchera pas une mauvaise expérience utilisateur.
- La clé serveur `stock_service_key` doit rester exclusivement dans `st.secrets` et jamais exposée au navigateur ou à GitHub. Les permissions Python sont requises, mais les RPC sont exécutées avec un rôle privilégié ; contrôler tous les chemins d'appel Streamlit.
- **Les tests locaux ne simulent pas les vraies transactions, les verrouillages PostgreSQL ni les droits Supabase.** Cette validation est bloquante.

## Appliquer le patch en local

```powershell
cd "C:\LH\Perso\ERP_PYT\erp-mortier"
git status
$patch = Join-Path $env:USERPROFILE "Downloads\correctif_achats_atomiques.patch"
Test-Path $patch
git apply --check $patch
# Seulement si aucun message d'erreur :
git apply $patch
.\.venv\Scripts\python.exe -m compileall -q app.py core config modules
.\.venv\Scripts\python.exe -m pytest -q tests/test_achats_atomic.py
# Autres suites connues, toutes sur mocks :
.\.venv\Scripts\python.exe -m pytest -q tests/test_app_security.py tests/test_auth_hardening.py tests/test_db_service_security.py tests/test_stocks_atomic.py tests/test_production_atomic.py tests/test_achats_atomic.py
git diff --check
git status
```

Si tout passe, commiter dans la même branche :

```powershell
git add modules/achats/service.py tests/test_achats_atomic.py sql/004_atomic_purchases.sql sql/achat_preflight_readonly.sql README_ACHATS_ATOMIC.md
git diff --cached --check
git diff --cached --stat
git commit -m "Preparer commandes et receptions atomiques"
git push origin correctif-db-service
```
