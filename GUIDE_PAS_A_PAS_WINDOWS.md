# Guide pas à pas : ERP Mortier / GitHub / Supabase (Windows)

**Ne pas exécuter la migration sur la base Supabase de production.**
Le correctif est un **module indépendant**. Son ajout à GitHub ne remplace pas les traitements des anciens modules de l'ERP.

## A. Déposer les fichiers dans GitHub, sans risque pour `main`

1. Télécharger `erp_mortier_patch.zip`, puis l'extraire sous Windows (clic droit > Extraire tout).
2. Ouvrir `https://github.com/Verwolfy/erp-mortier` en étant connecté avec un compte autorisé à écrire sur le dépôt. En l'absence de droits, créer un Fork.
3. Dans le sélecteur de branche (en haut, souvent `main`), saisir `securisation-erp-mortier` puis sélectionner **Create branch**.
4. Sur cette nouvelle branche, cliquer **Add file > Upload files**.
5. Déposer **les dossiers extraits** `erp_hardening`, `.github` et le fichier `INSTALLATION.md` (ainsi que ce guide si souhaité), **pas le ZIP**.
6. Vérifier que les chemins GitHub contiennent `erp_hardening/erp_engine/formulation.py`, `erp_hardening/sql/001_atomic_manufacturing.sql` et `.github/workflows/erp-hardened-tests.yml`.
7. Cliquer **Commit changes** et conserver la modification sur la branche de travail.
8. Ouvrir une **Pull Request** vers la branche principale. Ne pas fusionner et ne pas déployer avant tests sur Supabase de test.
9. Dans **Actions**, vérifier le workflow `ERP hardened core tests`. Il vérifie les calculs Python seulement, pas l'intégration SQL ni les écrans.

## B. Tester Python sur Windows (facultatif si Actions passe)

Dans PowerShell, à la racine d'une **copie locale** du dépôt contenant le dossier `erp_hardening` :

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install "pytest>=8,<10" "supabase>=2,<3"
$env:PYTHONPATH = (Resolve-Path .\erp_hardening).Path
.\.venv\Scripts\python.exe -m pytest -q .\erp_hardening\tests
```

Résultat attendu du correctif livré : `42 passed`. Ce ne sont **pas** des tests complets de l'ERP d'origine.

## C. Préparer Supabase de TEST

1. Dans `https://supabase.com/dashboard`, créer un projet distinct, par exemple `erp-mortier-test`. Ne pas utiliser le projet où sont les vraies ventes, factures et stocks.
2. Dans ce projet de test, ouvrir **SQL Editor > New Query**.
3. Ouvrir le fichier local `erp_hardening/sql/001_atomic_manufacturing.sql` dans un éditeur de texte, copier tout son contenu dans la requête et cliquer **Run**.
4. Si une erreur apparaît, ne pas continuer : conserver son message et faire corriger la migration. La migration n'a pas encore été validée sur une instance PostgreSQL réelle par son auteur.
5. Vérifier la création des tables par :

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'erp_hardening'
ORDER BY table_name;
```

Les tables attendues sont `company_members`, `items`, `recipes`, `recipe_lines`, `lots`, `operations`, `movements`.

## D. Créer un utilisateur de test et les données de démonstration

1. Dans Supabase **Authentication > Users**, créer un utilisateur email/mot de passe **de test**. Si nécessaire, marquer l'adresse de test comme confirmée. Copier son **UUID** utilisateur.
2. Dans **SQL Editor**, exécuter les requêtes suivantes, **une seule fois** :

```sql
-- Cette société et cette recette sont des IDENTIFIANTS DE DEMONSTRATION, pas ceux de l'ERP réel.
INSERT INTO erp_hardening.items (company_id, item_code, unit) VALUES
('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'RESINE', 'kg'),
('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'CHARGE', 'kg'),
('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'PEINTURE', 'kg');

INSERT INTO erp_hardening.recipes
(recipe_id, company_id, finished_item_code, base_quantity, status)
VALUES (
'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
'PEINTURE', 1000, 'DRAFT');

INSERT INTO erp_hardening.recipe_lines
(recipe_id, company_id, item_code, quantity) VALUES
('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'RESINE', 300),
('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'CHARGE', 700);

UPDATE erp_hardening.recipes SET status = 'APPROVED'
WHERE recipe_id = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
```

3. Autoriser votre utilisateur Supabase Auth de test : remplacer le texte `UUID_UTILISATEUR_AUTH` par **son UUID** dans cette requête, puis l'exécuter :

```sql
INSERT INTO erp_hardening.company_members (company_id, user_id, role)
VALUES (
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  'UUID_UTILISATEUR_AUTH',
  'admin'
);
```

**Très important :** les comptes Streamlit/bcrypt historiques de l'ERP ne donnent PAS un `auth.uid()` Supabase Auth. Le nouveau SQL exige une connexion par **Supabase Auth** et un utilisateur présent dans `company_members`.

## E. Test manuel bout en bout avec une vraie session Supabase Auth

1. Dans le tableau de bord du **projet de test**, relever l'URL du projet et sa clé **publishable** (`sb_publishable_...`) via **Connect** ou **Settings > API Keys**. Ne jamais utiliser une clé `sb_secret_...` ou `service_role` dans le test utilisateur.
2. Dans PowerShell, à la racine du dépôt, après avoir créé l'environnement Python ci-dessus :

```powershell
$env:PYTHONPATH = (Resolve-Path .\erp_hardening).Path
.\.venv\Scripts\python.exe .\erp_hardening\examples\test_manuel_supabase.py
```

3. Saisir l'URL et la clé publishable **du projet test**, puis l'email/mot de passe du compte créé dans Supabase Auth.
4. Le programme effectue trois opérations : réception de 300 kg de résine (avec test de rejouabilité), réception de 700 kg de charge, fabrication de 500 kg de peinture. La recette devrait consommer **150 kg de résine et 350 kg de charge**, coût matières total **650** unités monétaires de démonstration.
5. Contrôler ensuite les écritures réelles :

```sql
SELECT item_code, direction, quantity, unit_cost, created_at
FROM erp_hardening.movements
ORDER BY movement_id DESC
LIMIT 20;
```

Un succès de ce test manuel ne suffit pas pour déployer : il faut aussi exécuter **tous** les scénarios de `erp_hardening/SQL_VALIDATION_CHECKLIST.md`, y compris utilisateurs non autorisés et exécutions concurrentes.

## F. Connecter le nouvel ERP (travail restant)

- Adapter `modules/production/service.py`, `modules/achats/service.py` et `modules/stocks/service.py` aux signatures des RPC via `erp_engine.gateway.ERPGateway`.
- **Ne pas** laisser une opération écrire simultanément dans les anciens stocks et les nouvelles tables : établir une migration des données et un basculement contrôlé.
- Adapter la connexion existante à **Supabase Auth** par utilisateur, sans partager un client authentifié entre plusieurs sessions Streamlit.
- Prévoir synchronisation différée vers Google Sheets, gestion des annulations par mouvements inverses, journal d'audit, coûts de main d'œuvre et frais indirects, droits granulaires et contrôle qualité.
- N'autoriser une mise en production qu'après recette fonctionnelle, tests SQL sous charge, sauvegarde restaurable et procédure de retour arrière.

**Etat :** ajout de code = faisable maintenant; activation métier/production = non validée et non automatisée.
