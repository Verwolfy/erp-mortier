# REL-01 — Provenance du déploiement Streamlit, lot initial

## État précédent

L'ERP est testé sur le SHA de GitHub, mais l'observateur public `streamlit-shell-observe.yml` renvoie parfois HTTP 303 `share.streamlit.io`. Ceci **ne démontre ni quel commit est exécuté ni le bon fonctionnement authentifié**.

## Ce qui change dans cette PR

`core/release_provenance.py` calcule un indicateur **sans réseau** ; `app.py` l'affiche dans la barre latérale **après vérification du compte utilisateur et des droits**. Aucun SHA n'est exposé dans la page de connexion. Trois types de résultat :

| Observation | Message | Niveau de confiance |
|---|---|---|
| SHA de `.git/HEAD` lu par `git rev-parse HEAD` depuis la racine du déploiement | `checkout Git local` ; avec `ERP_RELEASE_EXPECTED_SHA`, `CHECKOUT CONFORME` ou `ÉCART DE VERSION` | Preuve du checkout disponible localement ; ne garantit pas à elle seule la totalité des fichiers exécutés ou la bonne connexion métier |
| Pas de `.git`, mais variable `ERP_DEPLOY_SHA` fournie | `déclaration non prouvée` / `NON VÉRIFIÉ` ou `ÉCART DÉCLARÉ` | Valeur déclarative, ne doit jamais être présentée comme preuve |
| Ni checkout local ni déclaration | `NON VÉRIFIABLE` | **Aucune preuve de version** ; exige recette authentifiée |

Un SHA invalide est rejeté ; aucune donnée d'environnement autre que deux SHA validés n'est affichée. L'indicateur n'exécute pas Git si `.git` est absent, et ne lance aucune connexion Supabase/Google Sheets.

## Procédure de recette authentifiée après livraison

1. Choisir le SHA **complet de la version de release** et configurer la variable de déploiement `ERP_RELEASE_EXPECTED_SHA` lors du prochain déploiement autorisé. Ne pas utiliser ce SHA comme preuve de version exécutée.
2. Se connecter à l'application Streamlit hébergée avec un compte habilité. Lire dans la barre latérale `Version ERP`, le SHA et la source d'observation.
3. Si `checkout Git local` et `CHECKOUT CONFORME` : enregistrer une capture de la section authentifiée, la date et le SHA attendu ; confirmer également les parcours métier.
4. Si `NON VÉRIFIÉ`, `NON VÉRIFIABLE`, `SHA attendu invalide`, ou `ÉCART` : **ne pas annoncer le commit comme effectivement déployé** ; examiner configuration Streamlit Cloud et historique des déploiements avant toute acceptation.
5. Ne jamais copier de clé Supabase, cookies, contenu de session ou données personnelles dans la preuve.

## Validation obtenue et limites

Les tests unitaires montrent comparaison correcte de deux SHA complets, absence de fausse preuve sur variable seule, signalement de l'écart et comportement sûr lorsque `.git` est absent. **La recette dans la véritable session Streamlit est toujours nécessaire** ; son résultat ne peut pas être inféré depuis les tests GitHub.

La migration PostgreSQL d'unicité des tiers demeure **en pause** ; aucun changement production ou des données `DEMO/SIM`.
