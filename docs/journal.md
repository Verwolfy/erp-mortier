# Journal d'exécution — Sofiane ERP

## 2026-11-08 — P0, sécurisation de l'outil de hachage

- Branche : `fix/p0-secret-input-gate-20261108`, issue de `main`.
- Remplacement de `mdp.py` : suppression d'une affectation littérale de mot de passe présente dans le dépôt public ; saisie désormais masquée et confirmation avant hachage bcrypt.
- Nouveau contrôle local `scripts/audit_credentials_source.py` : signale les affectations littérales sensibles sans afficher les valeurs. Il ne remplace pas `gitleaks` sur l'historique.
- Tests : `tests/test_password_hash_tool.py` et `tests/test_secret_source_guard.py`. L'exécution complète et la CI restent à vérifier avant toute fusion.
- Aucun identifiant réel ni mot de passe de l'ERP n'est stocké dans les modifications.
- L'authentification administrateur Streamlit n'a pas été exercée dans cette session : pas de navigateur distant utilisable. Ne pas déclarer la connexion vérifiée.
- Aucune migration, aucun changement de données, RLS, GRANT ou comptes utilisateur ; pas de modification du mot de passe ERP.
- Le secret précédemment présent dans l'historique Git nécessite une qualification et une rotation s'il a jamais été utilisé comme mot de passe actif.
- Une connexion à l'ERP et un changement de mot de passe restent à réaliser dans un navigateur sécurisé. Ne pas intégrer ces opérations à un workflow GitHub Actions.
- Règles maintenues : `DB-UNI-01` gelé ; tests d'intégration avec écriture uniquement dans un environnement Supabase TEST indépendant.

**Décision :** conserver le correctif sur branche et n'envisager la fusion sur `main` qu'après la suite complète et les contrôles de sécurité.
