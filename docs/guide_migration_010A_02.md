# ERP Mortier — 010-A-02 : contrôles GRANT / RLS / RPC

**Version de travail :** 24 octobre 2026 — contrôle préalable en lecture seule.
**Périmètre :** autorisations SQL de la branche `correctif-db-service`.

## À quoi sert cette vérification ?

Les scripts des migrations 002 à 009 **décrivent** les droits voulus ; cela ne prouve pas qu'ils ont été appliqués dans le projet Supabase effectivement utilisé.
Le rapport vérifie l'état des objets *déployés* : RPC, tables techniques, tables métier et schéma `public`.

- **GRANT / REVOKE** : droits SQL effectivement accordés aux rôles `anon`, `authenticated` et `service_role`.
- **RLS** : mécanisme de filtrage des lignes ; aucune politique RLS n'est pas automatiquement une ouverture des données.
- **RPC** : fonctions PostgreSQL qui exécutent les opérations atomiques de l'ERP.
- **service_role** : rôle serveur à privilèges élevés qui contourne habituellement la RLS ; ne jamais l'utiliser dans le navigateur ni lui donner une confiance métier sans contrôle applicatif.

## Procédure sûre : TEST uniquement

1. Vérifier dans Supabase que le projet ouvert est **TEST** et que son identifiant diffère de PRODUCTION.
2. Faire une sauvegarde/snapshot TEST si des opérations ultérieures sont envisagées.
3. Ouvrir SQL Editor et exécuter **uniquement** `sql/010A_02_permissions_audit_readonly.sql`.
   Cette requête ne contient qu'un `WITH ... SELECT` ; aucune création, écriture, révocation ni appel RPC.
4. Exporter le résultat tabulaire complet en CSV. **Ne pas fournir de secrets, URLs privées, mots de passe ni données clients.**
5. Sur le PC Windows, dans le dossier du projet, contrôler le CSV :

   ```powershell
   cd "C:\LH\Perso\ERP_PYT\erp-mortier"
   .\.venv\Scripts\python.exe -m scripts.verifier_audit_permissions_010a "C:\chemin\rapport_permissions_TEST.csv"
   ```

   Sans environnement `.venv` : `python -m scripts.verifier_audit_permissions_010a "C:\chemin\rapport_permissions_TEST.csv"`.

### Lecture des résultats

| Statut | Interprétation |
|---|---|
| `BLOQUANT` | RPC manquante, exécution non autorisée, droit excessif sur une table technique, etc. Correction requise avant activation du lot. |
| `A_VERIFIER` | Revue d'un administrateur/ingénieur requise ; ne pas automatiser une suppression de droits. |
| `INFO` | Constat sans certification de sécurité. |
| `OK` | Contrôle ciblé conforme ; ne certifie pas toute la sécurité de la base. |

Le vérificateur quitte avec un code 2 si un blocage est détecté, 1 si une revue est requise, 0 si aucune alerte n'est signalée, 3 si le rapport est incomplet.

## Points de compatibilité à examiner avant tout changement

- `modules/ventes/service.py` appelle `increment_compteur` avec `get_supabase_client()`, alors que `sql/007_secure_invoice_counter.sql` réserve son exécution à `service_role`. Vérifier quel rôle est réellement utilisé, sans jamais afficher la clé. Une modification des droits peut interrompre la numérotation.
- Les tables métier existantes peuvent être volontairement privées de politiques RLS, le serveur passant par `service_role`. Cela **n'autorise pas** une ouverture générale des tables à `authenticated` ou `anon`.
- Les fonctions déclarées `SECURITY INVOKER` ont besoin des privilèges et tables appropriés pour s'exécuter. Leurs tables techniques protégées n'impliquent pas que les tables métier sous-jacentes soient protégées de la même façon.
- Certains objets `erp_*` peuvent être absents parce que les migrations correspondantes n'ont jamais été installées. Le rapport doit alors signaler `BLOQUANT`, sans proposer de migration destructive par défaut.
- Le contrôle est limité aux objets `public` et aux rôles usuels. Il ne remplace pas un audit complet des schémas, des JWT, des vues, des fonctions propriétaires, des secrets, ni des accès réseau externes.

## Corrections : procédure de décision

1. Examiner et dater le rapport sur TEST, avec les écarts observés.
2. Rapprocher chaque fonction et table des migrations existantes, des appels Python et des droits d'utilisateur réels.
3. Rédiger un **script correctif distinct** avec effets détaillés et plan de retour arrière.
4. Tester l'accès autorisé **et** le refus de l'accès interdit sur TEST, avec les rôles pertinents ; tester les flux ventes, stocks, achats, production et finance.
5. Ne déployer sur PROD qu'après validation séparée et sauvegarde restaurable.

## Guide et Aide

Depuis l'ERP : **Guide et Aide → 🔎 Vérification des droits SQL (010-A-02)**. Cette rubrique est informative : elle ne contient aucun accès permettant de changer les permissions.

## Conditions de fin du lot

Ce script constitue le **diagnostic préparatoire de 010-A-02**, pas sa validation finale. L'audit reste en attente du rapport de TEST et des tests d'intégration SQL. Les résultats statiques Python ne valident pas la politique effective en base.
