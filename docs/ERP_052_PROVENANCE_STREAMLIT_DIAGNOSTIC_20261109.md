# ERP-052 — Provenance du code Streamlit : correctif, tests et blocage de déploiement

Date : 9 novembre 2026. Branche : `main`. Application : https://nextgent-erp.streamlit.app/

## Objectif
Suite à ERP-051, fiabiliser le SHA présenté par la barre latérale de l'ERP, détecter un checkout partiellement synchronisé et confirmer le déploiement sans contourner l'authentification, la sécurité comptable ou les règles TVA.

## Cause technique plausible et correctif
Le module `core/release_provenance.py` utilisait `@lru_cache(maxsize=1)` sur `_checkout_head()`. Dans un long processus Streamlit, la valeur `git rev-parse HEAD` pouvait rester figée après un changement Git sans redémarrage du processus. Ce mécanisme est **identifié dans le code**, mais il n'est pas démontré qu'il soit à lui seul la cause unique de l'écart hébergé.

Correctif `9933a1db663889034334853ff5ef0e05e53da229` :
1. Relecture de `git rev-parse HEAD` à chaque construction du texte de provenance ; pas de cache permanent.
2. Comparaison **en lecture seule** de trois sources critiques sur disque (`app.py`, `core/release_provenance.py`, `modules/ventes/views.py`) avec leurs objets Git dans `HEAD` via `git rev-parse HEAD:chemin` / `git hash-object -- chemin`.
3. Si écart : `ÉCART SOURCES/CHECKOUT` et `sources critiques : ÉCART AVEC GIT HEAD` affichés ; s'il est impossible de contrôler : `sources critiques : NON VÉRIFIABLES`.
4. Ni code source, ni credentials, ni noms de fichiers sensibles ni accès réseau transmis dans l'interface.

**Limite** : la concordance de ces trois fichiers ne certifie pas **tous** les modules, les dépendances, les caches Python déjà importés, ni la version GitHub attendue. Sans valeur `ERP_RELEASE_EXPECTED_SHA`, le SHA cible n'est pas fourni.

## Preuves CI
- Sept tests nouveaux dans `tests/test_release_provenance.py` : deux appels successifs avec HEAD différent, 3 fichiers concordants / modifiés, fichier manquant, dépôt indisponible, priorité de l'écart sur la déclaration attendue, mentions correctes dans le libellé.
- Commit de tests `d6229abe9fb285a62c0b9d8c18e6ce6fb1c00fea`.
- [CI GitHub (42665420781)](https://github.com/Verwolfy/erp-mortier/actions/runs/42665420781) : **3295 passed**, 1 warning, 0 failed.
- [Audit de réconciliation (42665420769)](https://github.com/Verwolfy/erp-mortier/actions/runs/42665420769) : **success**.

## Retest réel avec compte authentifié
[Run TinyFish de contre-vérification ERP-052](https://agent.tinyfish.ai/runs/ecc1ed77-503e-41d6-a737-7effbab6e0ff) :
- Session ERP `ADMIN` réussie via Bitwarden/TinyVault, sans partager d'identifiants.
- Texte barre latérale toujours : `Version ERP : 15a63bf9d77968b4c4d0b9b6ad74b614f68c3984 · checkout Git local · SHA attendu non fourni`.
- Ventes : `Version interface Ventes : SOF-ERP-20261109-TAX-READINESS-01`.
- La nouvelle mention `sources critiques` **N'APPARAÎT PAS**.
- Conclusion : le code corrigé sur GitHub **n'est pas observé comme exécuté** dans l'instance hébergée. Il n'existe donc aucune preuve que Streamlit serve `main` à jour.

[Run TinyFish de diagnostic Cloud](https://agent.tinyfish.ai/runs/1b5e4faf-e8c6-4380-9a64-5f02e8a07c78) :
- Le compte ERP ADMIN ne donne pas accès aux commandes Streamlit Cloud (aucun `Manage app` visible).
- Repo/branche/entrypoint réels de Community Cloud, journaux et commande Reboot **non accessibles** via cette authentification ERP.
- Aucun redéploiement, arrêt/redémarrage, suppression ni changement de secrets n'a été effectué.

## Décision de sécurité
**NE PAS** simuler un déploiement réussi, ne pas changer `requirements.txt` juste pour forcer un rebuild (version `streamlit>=1.38.0` non épinglée), ne pas modifier le moteur de facture ou activer TVA/SCF non qualifiés.

## Prochaine étape dépendante d'un compte distinct
Le propriétaire du déploiement doit accéder à **Streamlit Community Cloud** (https://share.streamlit.io/) avec son compte GitHub propriétaire :
1. Espace de travail correspondant au propriétaire du dépôt `Verwolfy`. Identifier la fiche de `nextgent-erp.streamlit.app`.
2. Vérifier repo source, branche, chemin d'entrée, dernier événement de synchro et logs ; comparer au GitHub `main` actuel.
3. Si ces paramètres sont conformes et la CI valide, utiliser la fonction **Reboot** officielle pour repartir du code source attendu. Attention : cette opération interrompt temporairement les utilisateurs ; ne pas la lancer sans visibilité sur l'instance.
4. Refaire l'authentification E2E et vérifier que le SHA sidebar n'est plus `15a63bf9`, que le suffixe `sources critiques` est présent et conforme, et que le marqueur Ventes reste cohérent.
5. Renseigner et vérifier un SHA attendu via la configuration de déploiement selon les contrats `core/release_provenance.py` (sans secret d'utilisateur), puis tester la concordance et les refus si mismatch.

Documentation officielle :
- https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app
- https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/reboot-your-app

Suivi GitHub : [Issue #78](https://github.com/Verwolfy/erp-mortier/issues/78) **OUVERTE**, commentaire ERP-052 publié.

## Invariants préservés
- Aucune écriture Supabase et aucun secret stocké dans le code ou les rapports.
- Supabase principal inchangé par ERP-052 ; base TEST non sollicitée.
- Les anomalies fiscales et Achats précédentes restent à traiter : [#76](https://github.com/Verwolfy/erp-mortier/issues/76) et [#77](https://github.com/Verwolfy/erp-mortier/issues/77).
- ERP-051 : 9 modules ouverts réellement sous ADMIN, **lecture seule** ; pas de preuve transactionnelle E2E.
