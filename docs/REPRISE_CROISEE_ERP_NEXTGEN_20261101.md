# Reprise croisée Sofiane ERP ↔ NextGen SiteWeb — 2026-11-01

> Journal de continuité de projet. **Lecture et consolidation uniquement : aucun déploiement Cloudflare, aucune écriture SQL métier, aucun changement RLS/GRANT, aucun secret activé dans ce lot.**

## Sources de vérité observées
- ERP : `Verwolfy/erp-mortier`, branche `main` ; tête auditée `d232cdbe312a650df4f4fc2eb75ae8160dfcafaf`.
- Site : `Verwolfy/nextgen-website` (privé), branche `main` ; tête auditée `4ad6ee3efef6d25c9c497471aad1f226d405f8df`.
- Supabase PROD : projet `wenydirqtmkywbxbxfal`, ACTIVE_HEALTHY. TEST `ffuhbmcfyexsbjwhryvj` INACTIVE, consultation impossible ; **ne pas réactiver sans nécessité**.
- Reconstruction à partir des fichiers persistés et connecteurs ; **le texte intégral de l'ancienne discussion « Sofiane/ SiteWeb Draft » n'est pas directement disponible**.
- Instruction : consulter aussi `docs/ETAT_AVANCEMENT.md` dans les deux dépôts et `prompt_execution_autonome.md` fourni au projet.

## Constats vérifiés le 01/11/2026
1. Site Astro 6 B2B **NextGen Building Solutions** FR / AR (RTL) / EN, maquettes d'emballages 3D ; pas de catalogue public réel approuvé et pas de collecte activée. Le dépôt privé n'implique pas un hébergement privé.
2. Requête SQL PROD en lecture seule : `public.site_produits = 50` lignes privées, `public.site_products = 0` ligne exportable, `public.site_demandes = 0`, `public.schema_migrations = 0`, `supabase_migrations.schema_migrations = 23`. **Ne pas confondre les deux historiques** ni inventer des entrées dans le premier.
3. `site_produits` et `site_demandes` : RLS actif (2 tables), zéro politique ouverte ; seuls les GRANT de `service_role` apparaissent pour ces tables, incluant toujours DELETE/TRUNCATE. Ne pas réduire ces droits sans arbitrage RLS/GRANT explicite.
4. CRM ERP : onglet demandes NextGen présent sur main ; lecture métadonnées seulement et **double verrou** `nextgen.crm_inbox_read_enabled is True` ET `nextgen.privacy_review_approved is True`; ne pas activer. Service de qualification SKU en lecture seule sur main ; ne débloque ni vente, ni production, ni publication.
5. Endpoint `functions/api/lead.js` : POST renvoie 503 tant que `NEXTGEN_LEADS_ENABLED !== 'true'`. Ne pas configurer les secrets ni activer la collecte sans revue juridique et tests préproduction.
6. Inventaire GitHub : huit branches historiques NextGen divergentes (4 ERP, 4 site), **aucune PR ouverte**. Tous les chemins des fichiers touchés existent déjà sur `main`. Comparaison des empreintes : 4/4 fichiers SKU ERP identiques, 2/2 fichiers empreinte CRM identiques, 5/5 fichiers lot 8 site identiques ; d'autres fichiers diffèrent entre branche ancienne et `main`, souvent par évolution postérieure. **Ne pas fusionner les branches anciennes aveuglément** ; faire une revue sémantique et tests avant décision. Ne pas supprimer les branches.
7. CI GitHub : sur la tête ERP `d232cdbe`, audit de réconciliation et tests lot C = `completed/success`. Sur la tête site `4ad6ee3e`, build Astro et recette navigateur = `completed/success`. Cela ne démontre **ni déploiement Streamlit du SHA**, ni protection Cloudflare, ni conformité juridique.
8. Supabase : avis sécurité `rls_enabled_no_policy` de niveau INFO, à contextualiser ; aucune modification SQL dans cette reprise.

## Interdictions et points d'arrêt
- **NO-GO** : publier Cloudflare Pages ou connecter le dépôt à Pages, changer DNS/domaine, activer l'API leads ou les deux verrous CRM, publier produits, certificats, FT/FDS ou prix non approuvés.
- La documentation Cloudflare précise que les previews Pages sont publiques par défaut et que la policy de preview **ne protège pas** d'elle-même le `<projet>.pages.dev` principal ; protéger et tester séparément l'origine primaire, les alias et URLs hash.
- Revue juridique obligatoire : notice FR/AR/EN, responsable du traitement, finalités, base légale, durée de conservation, sous-traitants/transferts et droits. Aucune durée ni conclusion légale inventée.
- Ne pas inventer tarifs, densités, recettes, paramètres fiscaux/SCF/CNAS ou informations fournisseurs ; `NON VÉRIFIÉE` et inactive en l'absence de preuve. Validation par expert-comptable algérien indispensable avant production fiscale.
- Demander accord pour suppression, secrets, RLS/GRANT, changements réglementaires à fort impact, publication externe et coûts. Aucun `force push`.
- L'utilisateur a indiqué qu'il ne souhaite pas de sauvegarde PostgreSQL ; **ne pas engager de modification de schéma risquée en l'absence de stratégie approuvée**.

## Prochain lot conseillé : qualification et vérification non destructives
1. Revoir les écarts de contenu résiduels de chaque branche ancienne par rapport à `main`, puis noter « intégré / obsolète / à reprendre » ; vérifier CI.
2. Vérifier l'ERP Streamlit hébergé **avec une session autorisée** : dépôt `erp-mortier`, branche `main`, entrée `app.py`, SHA/repère visible. Une réponse HTTP 303 anonyme n'est pas une preuve de déploiement.
3. Consolider les manques de 142 SKU NextGen identifiés dans `docs/LOT10_NEXTGEN_QUALIFICATION_READONLY.md` : aucun prix ni dossier fiscal, kits incomplets, densités/sources fournisseurs manquantes ; consultation seulement, pas de valeurs inventées.
4. Mettre au point en mode **offline** la recette Cloudflare Access / routes, sans site public ; recetter les 3 langues et la non-collecte ; ne déployer qu'après autorisations explicites.
5. Refaire la réconciliation des migrations Supabase sur historique natif et schéma réel ; `public.schema_migrations` vide ne prouve pas l'absence des migrations natives. TEST reste arrêté.
6. Après chaque lot : vérifier sources GitHub et SQL, CI, absence de secrets, puis mettre à jour ce journal et les journaux propres aux deux dépôts.

## Reprise rapide
- Site : `README.md`, `docs/LOT6_PREPRODUCTION_GATE.md`, `docs/LOT7_REGISTRE_DONNEES_ET_VALIDATION.md`, `docs/LOT8_CLOUDFLARE_PREPROD.md`, `docs/LOT9_ACCESS_VERIFICATION.md`, `docs/DEPLOIEMENT_CLOUDFLARE_RUNBOOK.md`.
- ERP : `docs/ETAT_AVANCEMENT.md`, `docs/LOT5_NEXTGEN_INBOX_READONLY.md`, `docs/LOT10_NEXTGEN_QUALIFICATION_READONLY.md`, `A_VALIDER.md`.
- Requête témoin : `SELECT (SELECT count(*) FROM public.site_produits), (SELECT count(*) FROM public.site_products), (SELECT count(*) FROM public.site_demandes);`.
- Source officielle Cloudflare : https://developers.cloudflare.com/pages/configuration/preview-deployments/ et https://developers.cloudflare.com/pages/platform/known-issues/.

**Dernière décision : CONTINUER les validations non destructives ; ARRÊT avant tout déploiement/activation ou modification des privilèges.**
