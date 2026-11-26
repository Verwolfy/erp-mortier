# Sofiane ERP — étude de sauvegarde PostgreSQL hors Supabase (26 novembre 2026)


> **STATUT AU 26/11/2026 : EN PAUSE — DÉCISION UTILISATEUR.** Projet de sauvegarde externe R2/B2 gelé jusqu'à la **fin de la phase de tests ERP**. Ne créer ni bucket, ni secret, ni workflow de sauvegarde externe ; ne pas activer la facturation R2 ; ne pas exécuter d'export. Reprise uniquement après constat de clôture de la phase de tests et décision explicite de relancer ce chantier. Le fonctionnement existant de Supabase, Google Sheets, Streamlit et du workflow keepalive est conservé. Les analyses ci-dessous restent une étude, non une sauvegarde opérationnelle.

## Mission et statut

**Étude réalisée ; aucune sauvegarde cloud n'a été créée, aucun bucket R2 activé, aucun nouveau secret ni accès SQL modifié.** Recommandation : **GitHub Actions + pg_dump PostgreSQL 17 sans Docker + chiffrement client (age) + bucket privé Cloudflare R2 Standard situé dans la juridiction UE**, après activation R2 et validation des nouveaux secrets/coûts. Backblaze B2 est la solution de repli.

## Faits vérifiés directement

- Dépôt : `Verwolfy/erp-mortier`, branche `main`.
- Supabase principal : projet `erp-mortier`, ref `wenydirqtmkywbxbxfal`, PostgreSQL **17.6**, région **eu-west-1**, statut **ACTIVE_HEALTHY** au contrôle.
- `pg_database_size(current_database())` = **18 205 843 octets** (« **17 MB** »), **101 tables** `public`, **5 vues** `public`. Ce nombre **n'est pas une mesure de la taille d'une archive pg_dump**.
- Supabase Storage : **0 buckets**, **0 objets** actuellement. `auth.users` : **0 utilisateurs**, `public.users` : **1 utilisateur** (seulement les comptages ont été lus).
- `core/db_service.py` et `core/sheets_service.py` : synchronisation de certaines données entre Supabase et Google Sheets. Certaines tables sensibles / historiques sont explicitement exclues (`_NO_SHEETS_SYNC`). **Google Sheets n'est pas une image reconstituable complète de PostgreSQL**.
- Le dépôt contient déjà `scripts/sauvegarder_supabase_pg.ps1`, utilisant **pg_dump custom** sans Docker, `PGSERVICEFILE` et `PGPASSFILE` hors dépôt ; le script produit un manifeste SHA-256 et teste `pg_restore --list`, mais **ce test ne prouve pas la restaurabilité**. L'existence du script ne démontre pas qu'une sauvegarde automatisée est actuellement opérationnelle.
- Le compte Cloudflare est accessible en lecture par connecteur. Requête `GET /accounts/{id}/r2/buckets` : **HTTP 403, code 10042**, message `Please enable R2 through the Cloudflare Dashboard.` **R2 n'est pas encore activé** ; aucune activation n'a été tentée.

## Comparatif (conditions officielles consultées le 26 novembre 2026)

| Option | Gratuité annoncée | Limites et décision |
|---|---|---|
| **Cloudflare R2 Standard** | **10 GB-mois/mois**, **1 million** opérations A/mois, **10 millions** opérations B/mois, egress gratuit | **Choix 1** : API compatible S3, stockage privé UE possible. Gratuit seulement dans le quota ; dépassements facturables. Le palier **Infrequent Access** ne bénéficie **pas** du quota gratuit. Activation du service/billing requise sur le compte actuel. |
| **Backblaze B2** | Premiers **10 Go toujours gratuits** ; transferts sortants gratuits jusqu'à **3×** le volume moyen stocké par mois | **Choix 2** : bonne alternative S3-compatible. Au-delà du quota, tarifs d'usage. |
| **Oracle Cloud Object Storage Always Free** | **20 Go** (Standard, Infrequent, Archive combinés) et **50 000 requêtes API/mois** sur les comptes Always Free concernés | Davantage d'espace, mais nouveau compte et configuration OCI supplémentaires ; contraintes de quota strictes, attention à la disponibilité des ressources. |
| **Google Drive compte personnel** | Jusqu'à **15 Go partagés** entre Drive, Gmail et Photos | Possibilité technique via OAuth/API, mais moins indépendant du fournisseur Google déjà utilisé par Sheets et quota partagé. |
| **AWS S3 nouveau compte** | Crédits AWS jusqu'à **200 USD** ; offre Free Plan de **6 mois maximum** | **Non recommandé** comme conservation gratuite durable ; attention à l'expiration de l'offre et aux éventuels coûts. Conditions différentes pour anciens comptes. |

Liens officiels :
- https://developers.cloudflare.com/r2/pricing/
- https://developers.cloudflare.com/r2/reference/data-location/
- https://developers.cloudflare.com/r2/reference/data-security/
- https://developers.cloudflare.com/billing/manage/spend-management/
- https://developers.cloudflare.com/changelog/post/2026-11-25-activate-pay-as-you-go-cli-mcp/
- https://www.backblaze.com/cloud-storage/pricing
- https://docs.oracle.com/fr-fr/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- https://support.google.com/accounts/answer/6374270
- https://aws.amazon.com/s3/pricing/
- https://aws.amazon.com/free/free-tier-faqs/

## Dimensionnement indicatif (non mesuré)

À titre purement illustratif : **30 × 17 Mo ≈ 510 Mo**, **90 × 17 Mo ≈ 1,53 Go** ; cela ne prédit pas la taille réelle de `pg_dump`, puisque les **17 Mo** sont une mesure physique de la base (incluant des overheads internes), pas du fichier de sauvegarde. Mesurer la première archive compressée/chiffrée et la croissance réelle avant de fixer les rétentions. Avec la taille actuelle, **R2 10 GB-mois paraît très largement suffisant** pour une sauvegarde quotidienne et plusieurs mois d'historique. L'offre R2 reste facturée à l'usage en cas de dépassement. Le plafond « 0 USD strict » **n'est pas garanti** par les simples alertes Cloudflare ; les limites de dépense documentées ne plafonnent pas directement R2.

## Architecture technique recommandée, sans Docker

1. **Planification** : GitHub Actions, quotidien (proposition **03h23 UTC**) et `workflow_dispatch`, jamais sur les PR ni sur fork. Permissions GitHub minimales `contents: read` ; aucune persistance de secret ni d'archive via les artifacts/logs.
2. **Cible sûre** : connexion PostgreSQL vers **la base principale seulement** (ref contrôlée). Installer/utiliser **pg_dump et pg_restore version 17** sur un runner éphémère. Pas de Docker. Via connexion PostgreSQL *directe* ou *session pooler*, pas la clé REST `SUPABASE_KEY`. Prévoir une identité SQL appropriée pour lire les données sauvegardées sans changer les privilèges existants sans accord.
3. **Périmètre à homologuer** : schéma et données ERP `public`, fonctions, triggers, RLS, GRANT, historique des migrations, et tout élément d'Auth/Storage nécessaire à la reprise. Le `pg_dump` PostgreSQL brut peut inclure des objets Supabase internes dont la restauration dans un autre projet nécessite des exclusions/adaptations : **une archive brute n'est pas une preuve de restauration Supabase intégrale**. S'assurer que les fichiers Storage physiques et les configurations extérieures à PostgreSQL sont traités séparément si le projet évolue.
4. **Contrôle local** : `pg_dump -Fc` ; vérifier le code de retour, le volume non nul, `pg_restore --list` et l'empreinte SHA-256. Pour une preuve suffisante, effectuer régulièrement une **restauration réelle en environnement isolé** (PostgreSQL 17 / projet de test approprié), avec comparaison schémas/données et tests métier, sans toucher à la production. Le projet TEST actuellement en veille **n'est pas réveillé automatiquement**.
5. **Chiffrement avant upload** : chiffrer l'archive avec `age` sous une clé publique de sauvegarde. **Clé privée de déchiffrement conservée hors GitHub, hors R2, hors Supabase**, avec copie de récupération contrôlée. Détruire les fichiers temporaires du runner à la fin du job ; ne pas journaliser les données.
6. **Upload** : objet immuable par horodatage, bucket **privé** R2 **Standard**, juridiction **UE** (et localisation Western Europe si possible). Clé/token R2 **limité au bucket**, avec le moins de droits possible. Aucun endpoint public `r2.dev`.
7. **Vérification à distance** : vérifier existence et taille de l'objet, SHA-256 du blob transféré ; à intervalles réguliers, télécharger et déchiffrer une archive dans un environnement sûr, puis lancer un test de restauration.
8. **Surveillance** : alerte sur échecs, fichier trop petit, absence de sauvegarde récente, capacité utilisée supérieure à **8 Go**. Les actions GitHub planifiées de dépôts publics peuvent être désactivées après **60 jours sans activité** ; le keepalive ne remplace pas une alerte sur des sauvegardes manquantes.
9. **Rétention** : proposition **30 quotidiennes + 12 mensuelles**, à confirmer après taille mesurée. **Aucune suppression automatique des anciennes sauvegardes sans accord explicite** (point d'arrêt du projet). Préserver les dernières sauvegardes saines si un nouveau run échoue.

## Sécurité et coût : points d'arrêt

- **Activation de R2** : non effectuée ; elle est bloquée sur le compte Cloudflare (403/10042). D'après la documentation Cloudflare de novembre 2026, l'activation nécessite un profil de facturation et un moyen de paiement. Ce **risque de facturation exige l'accord de l'utilisateur** avant l'activation. Le prix théorique attendu avec les volumes actuels est **0 USD/mois**, mais non garanti si dépassement des quotas.
- **Secrets GitHub et accès PostgreSQL** : le keepalive existant s'appuie sur une clé REST, **insuffisante pour un pg_dump complet**. Un identifiant de connexion PostgreSQL et les clés R2, isolés dans les secrets CI, sont nécessaires. Les nouvelles permissions, clés ou rotation sont des points d'arrêt selon les règles du projet.
- **Données de l'ERP** : données clients, employés et comptabilité ; bucket privé, chiffrement côté client et politique d'accès minimal. Vérifier les exigences de résidence et de transfert des données applicables avant stockage externe.
- **Aucune modification des RLS/GRANT, aucune migration, aucun export de données réelles ni coût externe réalisé pendant cette étude.**

## Prochaines actions si l'utilisateur autorise la mise en service

1. Valider **R2 Standard privé en juridiction UE** et activer la facturation R2 sous contrôle. Sinon choisir Backblaze B2 et adapter seulement la destination.
2. Qualifier le compte PostgreSQL dédié et les secrets nécessaires sans exposer de mot de passe (nouvelle clé ou permission : arrêt pour validation).
3. Implémenter un script portable `pg_dump` sans Docker et tests automatiques du pipeline ; réaliser **une première sauvegarde réelle et relever sa taille**.
4. Chiffrer, transférer dans R2, relire l'objet, vérifier les empreintes et documents de restauration.
5. Organiser **une restauration test réelle**, puis seulement activer la planification et la rétention approuvée. Mettre à jour `docs/ETAT_AVANCEMENT.md`.

## Limites documentées

- Supabase explique que ses exports et restaurations impliquent des schémas gérés particuliers ; voir https://supabase.com/docs/guides/self-hosting/restore-from-platform et https://supabase.com/docs/guides/platform/migrating-within-supabase/backup-restore.
- Les sauvegardes quotidiennes visent un **RPO ≤ 24 h si tous les jobs réussissent** ; aucune garantie de reprise tant que les tests de restauration n'ont pas été exécutés.
- R2 chiffre déjà les objets au repos, mais ce chiffrement géré par l'hébergeur ne remplace pas le chiffrement client de l'archive.
- Le script local du dépôt n'a pas été exécuté dans cette étude, et aucune exécution GitHub de sauvegarde cloud n'existe dans le cadre de cette étude.

**État final : ÉTUDE VALIDÉE POUR PRÉPARATION, DÉPLOIEMENT BLOQUÉ SUR ACTIVATION R2 ET GESTION DES SECRETS ; NE PAS PRÉTENDRE QUE DES BACKUPS EXTERNES EXISTENT.**
