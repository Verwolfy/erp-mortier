# Sofiane ERP — keepalive Supabase, suivi du 26 novembre 2026

## Objectif et choix

- Éviter autant que possible la mise en pause pour inactivité du projet Supabase principal **erp-mortier**, sans commits vides, redéploiements Streamlit, mutations SQL ou changements d'ACL/RLS.
- Dépôt : `Verwolfy/erp-mortier`, branche `main`.
- Projet principal : `wenydirqtmkywbxbxfal`, `https://wenydirqtmkywbxbxfal.supabase.co`, actif lors de la lecture initiale.
- Projet TEST : `ffuhbmcfyexsbjwhryvj`, **INACTIVE** lors de l'examen ; pas de réveil ni de ping ciblé.

## Découverte vérifiée (lecture seule)

- Les tables métier `public` sont protégées par RLS ; `anon` et `authenticated` n'ont pas `SELECT` sur `listes_reference`, `produits`, `site_produits`, `parametres`.
- `public.listes_reference` possède une colonne `id` (bigint) ; aucune écriture n'est nécessaire pour la consulter.
- Le workflow existant `.github/workflows/recalcul_stock.yml` référence `secrets.SUPABASE_URL` et `secrets.SUPABASE_KEY` pour un audit Supabase en lecture seule. **La présence effective / valeur des secrets n'est pas prouvée par la lecture du YAML.**
- Le nouveau workflow réutilise ces **noms** de secrets. Il vérifie que l'URL pointe exactement sur le projet principal avant toute requête. Une réponse HTTP 200 est exigée ; aucune donnée n'est imprimée.

## Implémentation

Fichier `.github/workflows/supabase-keepalive.yml` :

- Exécution aux heures UTC `07:17`, `15:17`, `23:17`, plus `workflow_dispatch` et déclenchement initial lors de l'ajout/modification de ce YAML sur `main`.
- Job Ubuntu, permissions GitHub minimales (`contents: read`), durée limite 3 min ; pas de checkout, pas de dépendances ni de commit.
- Requête HTTP PostgREST `GET /rest/v1/listes_reference?select=id&limit=1` utilisant les secrets GitHub Actions existants, résultat jeté, journalisation du seul code HTTP.
- Échec explicite si mauvais projet, secret manquant, erreur réseau ou HTTP différent de 200.
- **Aucune migration SQL, modification de données, modification RLS/GRANT ou rotation de clé.**

## Limites et suivi

1. Ce keepalive réduit le risque de pause, mais **Supabase ne garantit pas qu'un faible trafic suffise**. Seul un plan payant exclut la pause automatique.
2. GitHub peut retarder/omettre des planifications ; dans un dépôt public, GitHub désactive les workflows planifiés après **60 jours sans activité du dépôt**. Le keepalive ne crée pas de commit pour contourner cette limite.
3. La réussite du `curl` ne démontre ni le fonctionnement de Streamlit ni la disponibilité de l'ERP authentifié.
4. Vérifier dans **GitHub > Actions > ERP - Supabase principal keepalive (read-only)** le premier run, les exécutions suivantes et les erreurs éventuelles. Si `HTTP 401/403`, ne pas ouvrir RLS ni déposer une clé `service_role` supplémentaire automatiquement : qualifier la clé existante et demander validation de la stratégie d'accès.
5. GitHub Secrets ne sont pas lisibles en clair via le connecteur ; toute preuve réelle exige un run Actions réussi.

## Prochaine session

- Lire ce fichier et `docs/ETAT_AVANCEMENT.md` avant les prochaines phases ERP.
- Vérifier le commit du YAML sur `main` et les exécutions GitHub Actions réelles ; enregistrer SHA/run/conclusion. Ne jamais déclarer « tests OK » sans preuve.
- Ne pas toucher à la base Supabase TEST en veille et ne pas confondre test et principale.
- Reprendre ensuite la tâche ERP précédemment interrompue sans fusionner des branches ou migrations sans contrôles associés.

## Références

- https://supabase.com/docs/guides/platform/free-project-pausing
- https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows

## Déploiement et preuve du 26 novembre 2026

- Commit workflow sur `main` : `a15a6bbb3745b08b70448cea8a3edc7e593a0eea` ; fichier relu sur le dépôt après push.
- GitHub Actions : [run #45796762601](https://github.com/Verwolfy/erp-mortier/actions/runs/45796762601), déclenché par le push du workflow ; conclusion **success**, job `ping` **success**.
- Log horodaté à `2026-11-26T09:57:25Z` : `Supabase principal: SELECT en lecture seule confirme (HTTP 200)`.
- Ce succès confirme les secrets déjà existants suffisent **pour cette lecture** et que l'URL a été validée. Il **ne prouve pas encore les exécutions futures planifiées** ni la prévention garantie de la veille au-delà de sept jours.
- Aucun commit vide, aucun changement de configuration de Supabase ni déploiement Streamlit.
