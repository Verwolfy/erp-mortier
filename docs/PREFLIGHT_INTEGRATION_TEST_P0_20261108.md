# ENV-01 — Précontrôle de bac d'intégration isolé (P0, lot initial)

**Statut : verrou logiciel préparé, **aucune base TEST opérationnelle créée**. Ce lot est un préalable, **pas** une validation de tests RPC sur PostgreSQL. Aucun appel réseau ou mutation.

## Préconditions obligatoires avant tout essai avec écriture

La fonction `core.integration_test_guard.require_integration_test_target` reçoit les variables d'environnement et **refuse toute valeur absente ou ambiguë** :

| Variable | Conditions |
|---|---|
| `ERP_ENV` | Strictement `TEST`, jamais `PRODUCTION` |
| `ERP_PRODUCTION_SUPABASE_URL` | URL HTTPS réelle du projet production, uniquement comme identifiant de comparaison ; le précontrôle ne s'y connecte pas |
| `ERP_TEST_SUPABASE_URL` | URL HTTPS d'un projet TEST **distinct**, renseigné explicitement |
| `ERP_INTEGRATION_SUPABASE_URL` | Doit correspondre exactement au projet TEST autorisé |
| `ERP_INTEGRATION_CONFIRM` | Valeur exacte `I_CONFIRM_SEPARATE_TEST_DATABASE` |
| `ERP_TEST_SUPABASE_KEY` | Clé dédiée à TEST, non vide ; pas de clé de production déclarée identique |
| `SUPABASE_URL`, `ERP_RUNTIME_SUPABASE_URL` | Si présents, doivent eux aussi désigner TEST |

Le module réutilise le validateur `core/environment_guard.py` déjà existant ; il refuse un projet TEST dont l'URL est identique à celle de la production. Aucune configuration n'est générée automatiquement. **Ne mettre aucune vraie clé dans le dépôt, les logs ou les fichiers de démonstration.**

## Exécution du précontrôle

Après provisionnement autonome d'un projet TEST séparé, et uniquement dans le runner futur :

```bash
python scripts/preflight_integration_test.py
```

- Retour 0 : configuration déclarée correcte, **aucune connexion effectuée**.
- Retour 2 : configuration refusée, aucune connexion effectuée.
- Ce script ne crée ni schéma, ni fixture, ni test, ni mutation ; il ne peut à lui seul garantir l'isolement si du code ultérieur ignore son résultat.
- Des tests unitaires `tests/test_integration_guard_p0.py` couvrent refus production, URL erronée, alias vers production, clé partagée et non-fuite des valeurs sensibles.

## Phase suivante (non réalisée)

1. Provisionner une vraie base Supabase TEST indépendante de `wenydirqtmkywbxbxfal`, avec secrets distincts et périmètre financier/stock sans effet externe. Le projet de production ne doit jamais servir de bac.
2. Créer un exécuteur d'intégration qui **appelle ce précontrôle avant chaque ouverture de connexion** et réutilise uniquement la cible validée, puis charge des fixtures synthétiques éphémères.
3. Tester les transitions réelles (GOV-01), rejeux et race conditions (TX-01), séparations des tâches (SEC-01) ; journaliser uniquement les références de tests anonymes.
4. Nettoyer uniquement le projet TEST, prouver que la production n'a reçu aucune écriture. Les références `DEMO/SIM` de production restent intactes.

## Décisions conservées

La migration d'unicité PostgreSQL Clients/Fournisseurs reste **gelée sur demande de l'utilisateur**. Aucun index, trigger, migration, RLS/GRANT, secret ou changement de données de production à appliquer.
