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

## Addendum — revue des branches et qualification SQL du 01/11/2026

- **Revue sémantique des huit branches NextGen** : tous les fichiers touchés existent sur `main`. Les branches ERP « crm-ui-fingerprint » et « sku-qualification » correspondent exactement à `main` sur leurs fichiers. Les autres écarts sont des renforcements postérieurs déjà présents sur `main` (double verrou confidentialité CRM, lectures strictes du CRM, tests supplémentaires, contrôles CI Pages) ; la différence documentaire du runbook Cloudflare correspond à de l'échappement Markdown. **Décision : ne pas réintégrer les anciens états par merge**, préserver les branches comme archive jusqu'à décision de retrait.
- **Contrôle SQL de qualification NextGen PROD (lecture seule, direct)** : 50 produits actifs ; 142 SKU actifs ; **1 produit sans SKU : `PROOF-PU-SEAL`** ; 142/142 SKU sans tarif et 142/142 sans dossier fiscal ; 7 kits sans quantité nette ; 48 conditionnements liquides sans conversion ; 97 matières candidates actives. Il s'agit de manques opérationnels réels, **pas d'autorisation d'inventer les données**.
- Cette qualification confirme le choix de **ne rien activer côté vente, facturation ni publication catalogue**.

## Addendum Lot 11 — 01/11/2026, fin de cycle

- **ERP** : PR [#36](https://github.com/Verwolfy/erp-mortier/pull/36) fusionnée sur `main` par merge non destructif au SHA `81a0ebc68ebb220ed75b45635381d28919cfce68`. Les deux CI de ce SHA, audit de réconciliation et tests lot C, ont répondu `completed/success` : [audit](https://github.com/Verwolfy/erp-mortier/actions/runs/41320101825), [tests](https://github.com/Verwolfy/erp-mortier/actions/runs/41320101833).
- **Nouveau contrôle utilisateur** : sous Administration > Qualification TVA SKU, le `SECURITY_MANAGER` peut exporter un CSV local du diagnostic NextGen, sans secrets, prix ni données personnelles ; la colonne de preuve reste vide et le statut reste `NON_VERIFIE`. Droits recontrôlés au téléchargement ; anti-formule ; échec fermé pour snapshots invalides.
- **Documentation** : `docs/LOT11_NEXTGEN_EXPORT_SUIVI.md`, guide utilisateur et `docs/ETAT_AVANCEMENT.md` de l'ERP actualisés ; commit ultérieur de documentation `e0b3a990d491f41fde67356f455875416f616994`, CI de ce commit à vérifier indépendamment si nécessaire.
- **Migration SQL** : 23 migrations réellement inscrites dans `supabase_migrations.schema_migrations` (21 ERP et 2 site), zéro dans le registre applicatif distinct `public.schema_migrations`. Les 48 entrées de `erp-mortier/sql/` comprennent des brouillons, préflights et rollbacks, **ne pas les appliquer en bloc**. Aucun schéma modifié.
- **Blocages** : 142 SKU sans tarif ni dossier fiscal ; 7 kits incomplets, 48 liquides sans conversion, un produit `PROOF-PU-SEAL` sans SKU, 97 matières candidates ; catalogue web exportable vide. Aucune activation commerciale, fiscale, collectes leads ou publication Cloudflare.
- **Prochaine action** : confirmer le déploiement Streamlit **après authentification et inspection de la version**, recueillir les preuves réelles des SKU hors du dépôt public et établir les correspondances exactes des scripts SQL avec l'historique natif. La protection Cloudflare Access + approbations juridiques restent une condition avant préproduction.

## Addendum lot 12 — 01/11/2026 : exhaustivité des lectures ERP NextGen

- PR [ERP #37](https://github.com/Verwolfy/erp-mortier/pull/37) fusionnée sur `main` : SHA `6dfbf7005bb2f4196f9ccfe20950706a587eb6f6`.
- Les inventaires NextGen `produits`, `sku_conditionnement`, `matieres_premieres`, `erp_sku_fiscalite` sont lus par pages contrôlées avec `count=exact`, ordre des clés primaires et `SECURITY_MANAGER` à chaque page ; pas d'export s'il manque des lignes ou si un résultat est incohérent.
- `erp_sku_fiscalite` est identifié par `(sku_id,date_effet)` (clé composite SQL confirmée). Aucune version fiscale n'est interprétée comme validation implicite.
- Les tests couvrent une limite backend à 17 lignes sur 142 SKU, des variations de total, une page vide, des doublons et le retrait des droits entre pages.
- **Preuves CI** du commit fusionné : [suite complète ERP](https://github.com/Verwolfy/erp-mortier/actions/runs/41325282927) `success`, [tests facturation](https://github.com/Verwolfy/erp-mortier/actions/runs/41325283076) `success`.
- SQL de production lu sans écriture : **50 produits actifs, 142 SKU actifs, 119 matières premières, zéro dossier fiscal SKU**. Les blocages documentaires du lot 10 restent ouverts.
- Aucune modification des permissions, du schéma, des prix, des secrets ou du catalogue exporté. **Le site NextGen et ses formulaires restent inactifs** ; la CI ne démontre pas que Streamlit héberge la dernière version ni qu'une protection Cloudflare Access soit opérationnelle.
- Limite connue : les quatre lectures successives ne constituent pas un snapshot transactionnel intertables.
- Prochaine action : audit connecté de la version Streamlit réelle, puis qualification documentaire réelle des 142 SKU. Ne pas inventer pièces, prix, TVA, densités ou fournisseurs.

## Addendum Lot 13 — 01/11/2026 : réconciliation de migrations sans SQL

- ERP : PR [#38](https://github.com/Verwolfy/erp-mortier/pull/38) **fusionnée** sur `main` au commit `2f35e243fc410e49bcd8ca4c99d278c871b1b73d`. Deux CI de PR vertes : [audit](https://github.com/Verwolfy/erp-mortier/actions/runs/41326198104) et [tests](https://github.com/Verwolfy/erp-mortier/actions/runs/41326198126). Le statut des CI du merge doit rester distinct.
- Nouveaux fichiers ERP : `docs/migration_evidence_20261101.json` (23 migrations nominales), `scripts/auditer_preuves_migrations.py` (SHA-256 local et vérification **hors ligne**), `tests/test_auditer_preuves_migrations.py`, `docs/LOT13_AUDIT_PREUVES_MIGRATIONS.md`, et ajout à `docs/ETAT_AVANCEMENT.md`.
- Production Supabase `wenydirqtmkywbxbxfal` : **23** entrées dans `supabase_migrations.schema_migrations` (21 ERP + 2 site), **0** entrée dans `public.schema_migrations`. Les 4 premières versions ERP (012–015) ont des archives historiquement déclarées appliquées, la version 013 en six segments ; 016–018 ont des brouillons de thème similaire ; 019–032 ont des candidats ; les 2 scripts Site repérés dans le dépôt restent des **propositions non exécutées**. Aucun hash ne prouve le SQL réellement exécuté.
- Conseils Supabase sécurité : **86 INFO `rls_enabled_no_policy`**. Une absence de politique est compatible avec une stratégie de refus direct, à vérifier au cas par cas. Les tables sensibles citées ont RLS et n'accordent pas SELECT à `anon`/`authenticated`. **Aucune modification RLS/GRANT.**
- Les mises à jour du tableau de bord ERP survenues parallèlement ont été conservées lors de la fusion (pas de remplacement des fichiers métier concernés).
- **Aucune écriture Supabase**, aucun remplissage de registre, aucun déploiement Cloudflare, aucune activation de collecte, aucun SKU/tarif/TVA fictif.
- Limite Streamlit : accès HTTP externe/DNS indisponible depuis l'environnement ; ni le déploiement de la version réelle ni l'authentification n'ont pu être vérifiés.
- Prochaine priorité : preuve du SHA Git hébergé après connexion Streamlit ; comparaison réellement documentée version par version des migrations SQL ; qualification NextGen sur pièces vérifiées. Ne pas exécuter les fichiers SQL sur la seule base de leur nom.
