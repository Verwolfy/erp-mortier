# ERP Mortier — ETAT D'AVANCEMENT (28 octobre 2026)

## Phase en cours
**Phase 0 et réconciliation — audit complémentaire, sans migration.**
Ce fichier reprend les contrôles factuels. Ne pas annoncer la réconciliation terminée.

## GitHub
- Branche principale observée : `main` à `ec98ad5792c981e80b3956fa7cd0a2de905d03a7`.
- Inventaire : 10 branches distantes, 0 PR ouverte avant la branche d'audit.
- `correctif-db-service`, `preparation-sync-bdd-20261027` et sept autres branches historiques : aucun contenu manquant de `main` dans les fichiers comparés ; `feat/reglementation-lot-c-socle-20261028` possède un commit divergent, mais le fichier SQL 012 a le même blob SHA sur les deux branches.
- **Non vérifié** : états du poste Windows, `git status`, `git stash list`, commits locaux non poussés, tags et branche de déploiement Streamlit.
- Les changements locaux historiques connus (`README.md`, `modules/help/views.py`, `scripts/sauvegarder_google_sheets.py`) doivent être préservés ; ne pas appliquer un `git reset` ni une fusion locale non revue.

## Supabase
- TEST `ffuhbmcfyexsbjwhryvj`, PRODUCTION `wenydirqtmkywbxbxfal`.
- Les 2 projets contiennent 81 relations public (tables/vues), 549 colonnes, 178 contraintes, 95 index, 23 fonctions, 6 triggers, 4 politiques, 5 extensions. Empreintes de ces catégories identiques, sauf les permissions des relations.
- **66 différences de droits ACL** entre TEST et PRODUCTION. Ne pas uniformiser sans une décision explicite sur chaque famille de permissions.
- La table `public.schema_migrations` contient **0 ligne** dans chaque projet. Historique interne Supabase : 4 migrations sur TEST et 8 sur PRODUCTION, dont les quatre migrations historiques absentes de l'historique TEST.
- Comptages : 7 clients, 1 facture, 0 employé sur chaque projet ; impossible d'affirmer qu'il n'y a aucune donnée réelle.
- Les migrations additives 016 à 019 ont déjà été enregistrées dans les deux bases ; ne pas les rejouer à l'aveugle.
- Les paramètres réglementaires et règles sont toujours à 0 ; aucune activation de calcul fiscal n'est possible sans valeur juridiquement validée.

## Audit du code
- Les taux fiscaux sont encore codés dans `modules/ventes/service.py` et l'historique `sql/005_atomic_sales.sql` : `TAUX_TVA`, `TAUX_TIMBRE`, `MAX_TIMBRE`, calculs littéraux.
- `sql/013_facturation_parametree.sql` est une **proposition non appliquée** ; l'activer sans données validées bloquerait la facturation.
- Nouveau contrôle : `scripts/auditer_parametres_reglementaires.py` et tests de détection. `--strict` retourne un code d'échec sur les écarts. Scanner volontairement incomplet (à élargir au référentiel total), jamais une certification fiscale.

## Points d'arrêt (non levés)
1. Décision du 28/10/2026 : l'utilisateur ne souhaite pas de sauvegarde PostgreSQL. Cette étape est facultative et ne doit pas être proposée comme prérequis ; aucune sauvegarde ne sera lancée automatiquement.
2. Changement de RLS/GRANT/permissions non autorisé au cas par cas, avec 66 écarts. Ne pas répliquer automatiquement les permissions PRODUCTION plus larges vers TEST.
3. Chargement de taux, seuils, barèmes, échéances non autorisé avant vérification primaire et validation.
4. Synchronisation locale Git, revue de tous les secrets de l'historique, rejouabilité complète sur une base vierge, tests de bout en bout sur `main`/PRODUCTION non démontrés.
5. L'ensemble des lots C-H, y compris les déclarations fiscales officielles et le Guide & Aide complet, reste partiellement développé.

## Décision et prochaine action
**CONTINUER** les tests, diagnostics, guides et corrections de code sans écriture métier risquée.
**ARRÊT POUR VALIDATION** avant toute migration supplémentaire en base, toute homogénéisation des droits, et toute activation des calculs réglementaires.

La validation par un expert-comptable algérien est nécessaire avant toute production réglementaire.


## Lot Finance / Quittances — branche de travail

Nouveau moteur pur `core/quittances_rapprochement.py` : rapprochement des
encaissements, lettrages et factures, y compris paiements partiels et un
règlement affecté à plusieurs documents. L'interface Finance charge une
synthèse non fiscale seulement à la demande, avec contrôle des droits.
Tests de refus si le registre est incomplet ou incohérent.

Aucun reçu fiscal officiel et aucune écriture SQL ne sont émis par ce
module. Les 6 taux fiscaux fixes détectés par l'audit ne sont pas encore
remplacés : maintien du circuit actuel pour éviter une rupture de facturation.

---

## Point d'exécution du 29 octobre 2026 — PR 15, 16 et 17

**Branche principale GitHub fusionnée : `d3a083d688d79fde15740b093f564f78cf739f46`.**
Tous les workflows de la PR 17 sont verts, **1 547 tests ERP réussis**.
Aucune migration ou écriture Supabase effectuée pendant ces trois PR.

### Réalisé

1. **PR #15 — correctif Finance** : enregistrement de
   `erp_recus_internes` dans `core.db_service.SCHEMA_CONFIG` ; lecture
   autorisée aux profils Finance habilités, sans `operation_id` exposé
   dans la projection et sans insertion/mise à jour hybride.
2. **PR #16 — pré-audit Finance → SCF** : contrôle en lecture seule des
   écritures associées aux règlements `REGF-` : présence de deux lignes,
   débits/crédits équilibrés, types de comptes, dates, sommes exactes,
   écritures orphelines ou anciennes. Les règlements historiques non RPC
   sont exclus de la certification et dénombrés.
3. **PR #17 — calcul fiscal dormant** : interdiction d'appliquer l'ancien
   timbre de facture à 1 % plafonné à 2 500 DA dans le simulateur
   `core/fiscalite_facturation.py`. Rejet avant lecture réglementaire.
   **Le circuit de facturation effectif reste inchangé** et conserve
   encore les calculs historiques.

### État réel des registres Supabase, constaté le 29 octobre

Sur TEST et PRODUCTION : **zéro** plan de comptes SCF, exercice SCF,
journal SCF, règle réglementaire, paramètre réglementaire, règlement et
accusé d'encaissement. Les nouvelles tables sont installées, mais ne
contiennent aucune configuration métier permettant un usage réglementaire.

### Priorités restantes — selon la décision technique recommandée

| Priorité | Chantier | Condition pour terminer |
|---|---|---|
| P1 | Remplacement de la facturation et du timbre historique | Classifier chaque SKU (normal, réduit, exonéré), régime fiscal de l'entreprise, faits générateurs, avoirs, règlement réel et règles datées ; tester RPC de vente en transaction sur TEST |
| P1 | Comptabilité SCF réelle | Valider et charger un plan de comptes adapté, journaux, exercice, schémas d'écritures, idempotence de chaque source ; importer uniquement après contrôles |
| P1 | Paie et déclarations IRG/CNAS | Barèmes et assiettes officiels, cas salariés, preuves datées, tests de retenues et déclarations ; revue réglementaire |
| P2 | Test bout en bout transversal | Ventes → facture → règlement → accusé → écriture → SCF, achats → stock, paie → SCF, rapprochements des avoirs et annulations |
| P2 | Permissions TEST vs PRODUCTION | 66 écarts ACL sur tables historiques ; garder la restriction de TEST tant qu'un besoin concret ne démontre pas une permission manquante |
| P2 | Déploiement Streamlit | Branche réellement déployée et commit exécuté inconnus : la fusion GitHub ne garantit pas la mise à jour de l'application |
| P3 | Guide & Aide | Compléter la documentation des traitements officiels réellement activés et des procédures d'incident |

**Décision de sécurité conservée :** la sauvegarde PostgreSQL est facultative
à la demande du propriétaire ; aucun `pg_dump` automatique.

**Limite majeure :** ne pas interpréter les 1 547 tests comme une conformité
fiscale algérienne complète. La DGI publie des taux généraux de TVA de 19 %
et 9 %, mais l'application de ces taux dépend du régime fiscal et de la
classification des opérations. Le Code du timbre consolidé 2026 est publié,
mais le parcours fiscal réel d'encaissement et de quittance n'est pas activé.

Sources :
- https://www.mfdgi.gov.dz/fr/professionnels/services-pro/regime-reel/la-taxe-sur-la-valeur-ajoutee
- https://www.mfdgi.gov.dz/fr/a-propos/actu-fr/codes-fiscaux-fr
- https://www.mf.gov.dz/images/pdf/loidefinance/Loi_de_finance_2025_FR.pdf

**Prochaine étape réalisable sans hypothèse fiscale :** poursuivre les
interfaces de configuration et l'audit des taux/écritures en lecture seule.
Les paramètres métier et les homologations ne peuvent pas être inventés
pour accélérer la mise en production.


## Référentiels officiels 2026 — migration 021 installée

En date du 29 octobre 2026, le lot 021 est présent sur TEST et
PRODUCTION : deux taux de référence TVA DGI (19 % normal, 9 % réduit),
une règle G50 du régime réel et 25 comptes issus de la nomenclature SCF.
**0 compte actif ou mouvementable**, 0 exercice et 0 journal : aucun
mouvement SCF n'est initié automatiquement. Le code TVA universelle
`TVA_VENTE_TAUX` reste inexistant ; la facturation active n'est pas modifiée.

Dossier des sources, limites et preuves :
`docs/REFERENTIELS_OFFICIELS_2026.md`.
La classification des SKU, le régime fiscal effectif de l'entreprise,
les règles de timbre, les barèmes IRG/CNAS et les imputations SCF
demeurent à qualifier : **aucune valeur métier fictive** n'est utilisée.


---

## Actualisation vérifiée — 29 octobre 2026 (reprise autonome)

### Résultat de l'action précédente
- Dossier de reprise publié sur `main` : `docs/SOFIANE_ERP_DOSSIER_PROJET_2026-10-29.md`, commit `e07eeb501ea9894a97c64464c442e6f4d9a39b2f` ; contenu relu après publication.
- Dernier correctif RH constaté avant cette publication : `0ffe8c078d879222b6b12860adb675c204eace54`, dont le message revendique **1 720 tests**. Aucune exécution de pytest indépendante pendant cette reprise.
- Aucune PR ouverte au moment de l'interrogation GitHub.

### Contrôles SQL exécutés en lecture seule
Pour PRODUCTION `wenydirqtmkywbxbxfal` **et** TEST `ffuhbmcfyexsbjwhryvj`, requête `SELECT COUNT(*)` sur les cinq tables ci-dessous :

| Table | PRODUCTION | TEST |
|---|---:|---:|
| `public.parametres_reglementaires` | 5 | 5 |
| `public.regles_reglementaires` | 1 | 1 |
| `public.scf_plan_comptes` | 25 | 25 |
| `public.erp_sku_fiscalite` | 0 | 0 |
| `public.schema_migrations` | 0 | 0 |

Les historiques internes Supabase listent les migrations **016 à 024 sur les deux bases** ; la production liste aussi 012 à 015. La présence des tables et les comptages **ne démontrent pas** la validité juridique, les droits précis ni l'égalité exhaustive des schémas.

### Décisions de contrôle
- Aucune migration supplémentaire appliquée dans cette reprise.
- Aucune écriture réglementaire, RLS/GRANT, suppression ni sauvegarde PostgreSQL.
- Ne pas activer automatiquement la facturation fiscale, les écritures SCF ou la paie réglementaire sur les seuls nombres observés.
- Les anciennes affirmations d'absence de toutes les références fiscales ou SCF sont **historiques** et remplacées par les comptages ci-dessus ; les modules demeurent non certifiés.

### Prochaines étapes
1. Inventaire exhaustif des branches/commits et des migrations du dépôt, comparaison avec les historiques et schémas des deux bases.
2. Lire les 5 paramètres et la règle (code, statut, dates et provenance), sans en déduire un taux applicable par défaut.
3. Contrôler les ACL et politiques RLS sans les modifier.
4. Vérifier les tests CI ou exécuter pytest dans un environnement autorisé, puis contrôler le déploiement Streamlit effectivement servi.
5. Compléter les tests de bout en bout, l'administration des paramètres et les règles SCF/fiscales avec sources officielles et validation requise.

**État global : EN COURS.** Réconciliation et conformité réglementaire non démontrées.

### Vérification complémentaire des statuts du registre (29/10/2026)
La lecture SQL des cinq codes montre un état identique sur TEST et PRODUCTION : `TVA_TAUX_NORMAL` et `TVA_TAUX_REDUIT` sont `en_vigueur` depuis le 01/01/2026, sans date de fin ; `CNAS_REG_GENERAL_EMPLOYEUR_REF`, `CNAS_REG_GENERAL_SALARIE_REF` et `CNAS_REG_GENERAL_FONDS_OEUVRES_REF` sont `a_confirmer` sur la période 01/01/2026–31/12/2026. **Ne pas déclencher de calcul CNAS automatique sur ces trois références documentaires.** Le statut TVA seul ne prouve pas l'assujettissement d'une opération ou d'un SKU. Contrôle des sources, valeurs et fonctions de calcul encore nécessaire.


## Consolidation des branches — 29/10/2026
- Branche cible exclusivement : `main`.
- 31 branches secondaires comparées à `main` via GitHub compare_commits.
- 30 branches : `ahead_by=0` ; leur historique est inclus dans `main`.
- Exception : `feat/reglementation-lot-c-socle-20261028`, `ahead_by=1`. Son fichier divergent `sql/012_reglementation_registre.sql` a exactement le même blob SHA `bc742ac1d964347a55e02324ad34137434a848da` sur la branche et sur `main` : le contenu utile de ce fichier est déjà repris. Le commit en tant que tel n'est pas dans l'ascendance de `main`.
- Aucune suppression de branche GitHub ou de projet Supabase n'a été réalisée : les outils disponibles ne fournissent pas actuellement l'action de suppression. Ne pas présenter le nettoyage comme terminé.
- La base de TEST `ffuhbmcfyexsbjwhryvj` existe encore ; PRODUCTION `wenydirqtmkywbxbxfal` reste la cible de travail.
- La copie locale Windows `C:\LH\Perso\ERP_PYT\erp-mortier` n'est pas accessible depuis les connecteurs. Préserver les modifications non commitées avant synchronisation.
- Prochain objectif : nettoyage distant via un accès GitHub permettant de supprimer les références, fermeture de TEST via les contrôles Supabase, puis synchronisation locale contrôlée.


## Lot fiscalité — tests datés du 29 octobre 2026
- Ajout sur `main` de `tests/test_fiscalite_facturation_dates_2026.py`, commit `bdf12a50529c2913c5d07e7c70f77c98ced09214`.
- Couverture : changement de date d'effet, rétroactivité, arrondis Decimal, statuts non confirmés, chevauchement, absence, montants invalides, source absente et refus du timbre sur facture.
- Tests publiés, **non exécutés dans cette session**. Vérification de lecture du fichier GitHub réalisée. Les outils GitHub interrogés n'ont fourni aucun statut CI ou workflow PR pour ce commit. Ne pas conclure « tests verts ».
- Aucune migration SQL ni écriture de donnée métier effectuée. La facturation historique sur `main` n'est pas encore remplacée.


## Reprise technique — 29 octobre 2026
- Vérification de lecture du moteur fiscal et des nouveaux tests datés sur `main` : fichiers présents.
- Essai de récupération du dépôt depuis l'environnement Python : échec DNS `Could not resolve host: github.com`. Les tests du dépôt exact ne sont donc pas exécutés dans cet environnement.
- Aucun statut GitHub CI disponible lors du contrôle précédent pour le commit des tests `bdf12a5` ; aucune validation pytest annoncée.
- La modification des taux opérationnels ou le remplacement de la RPC fiscale reste conditionné à la qualification des SKU et à des tests de bout en bout.
- Dossier Markdown local de reprise actualisé avec cette limite. Aucune modification de la base principale.


## Vérification Python ciblée — 29 octobre 2026
- Deux fichiers récupérés par GitHub connecté : `core/fiscalite_facturation.py` (blob `001c45209ac34c3e898d1397ed0719a78389adeb`) et `tests/test_fiscalite_facturation_dates_2026.py` (blob `3afdefcb31cf2cd4e9929327edd10db123d55629`).
- Copies textuelles de ces fichiers exécutées dans un répertoire temporaire isolé, sans connexion SQL.
- Commande : `python -m pytest -q tests/test_fiscalite_facturation_dates_2026.py`.
- Sortie observée : `15 passed in 0.07s` ; **15 tests ciblés réussis**.
- Limite : ce contrôle ne certifie pas la suite complète ERP, le comportement de la RPC en production ni le déploiement Streamlit. Aucun changement de base effectué.
- Prochaine étape : sécuriser la transition du service historique de ventes (taux/timbre) en conservant la concordance RPC et la qualification juridique des SKU avant activation.


## CI fiscalité automatique sur main — 29 octobre 2026
- Workflow `.github/workflows/lot_c_tests.yml` étendu aux pushes sur `main` et au fichier `tests/test_fiscalite_facturation_dates_2026.py`.
- Commit de configuration : `9899d2fa4931c608df253020f7eed48a86999469`.
- GitHub Actions run https://github.com/Verwolfy/erp-mortier/actions/runs/40902978928 : **status completed, conclusion success** (consultation de l'API GitHub).
- Ce workflow inclut la suite complète `python -m pytest -q` dans son script. La conclusion `success` témoigne du succès du workflow, mais les nombres précis de tests ne sont pas extraits dans cette reprise.
- La publication du présent suivi peut déclencher une nouvelle exécution CI ; distinguer chaque run et son SHA.
- Aucune écriture Supabase ni activation fiscale dans cette étape.


## Tests fiscaux complémentaires — 29 octobre 2026
- Commit `46e80a89e9a00bd067ab96437228cd7f47713ed8` : 4 contrôles ajoutés aux tests fiscaux datés (unité incompatible, date illégale, montant booléen, variation du taux sans modification du code).
- Workflow déclenché sur `main` : https://github.com/Verwolfy/erp-mortier/actions/runs/40903575162. Statut observé durant cette étape : `in_progress`, conclusion non connue au moment de cette note.
- Le lot C précédent `a2f82368ab2a1a5d911182d3fe8cd8f1c7da9159` dispose d'un workflow `success` : https://github.com/Verwolfy/erp-mortier/actions/runs/40903121197.
- Aucune activation fiscale ni migration de la base principale ; l'ancien calcul de ventes reste présent en production et doit être remplacé seulement avec concordance SQL/Python et classification fiscale juridiquement validée.


## Validation CI confirmée — 29 octobre 2026
- Les exécutions du commit `46e80a89e9a00bd067ab96437228cd7f47713ed8` ont été **annulées** par la concurrence des workflows, et non déclarées réussies.
- Sur le commit suivant `baeeb3073868e435ded4381c3372fd0cbf15b9cc`, les workflows GitHub Actions `40903656833` et `40903656894` sont `completed / success`.
- Le job `tests` de l'exécution `40903656833` confirme deux étapes vertes : « Tests du socle fiscal » et « Tous les tests ERP (sans secrets et sans acces production) ».
- Preuve : https://github.com/Verwolfy/erp-mortier/actions/runs/40903656833 ; https://github.com/Verwolfy/erp-mortier/actions/runs/40903656894.
- Ce résultat valide la CI du code, pas la conformité juridique ni les fonctions SQL réellement déployées sur Supabase. Aucune migration appliquée à cette occasion.


## Concordance RPC en production — contrôle lecture seule du 29 octobre 2026
- Interrogation de `pg_proc` sur PRODUCTION `wenydirqtmkywbxbxfal` : une fonction `public.erp_sale_transaction(p_action text, p_operation_id text, p_payload jsonb)` existe.
- Aucune fonction `public.erp_facture_parametre` ni `public.get_param` trouvée sous ces noms dans le schéma `public` par cette requête.
- Conséquence : **le moteur fiscal SQL paramétrable n'est pas encore démontré installé**. Le fichier `sql/013_facturation_parametree.sql` reste un brouillon non appliqué. Ne pas remplacer le calcul Python isolément, car la RPC doit contrôler les mêmes règles et dates.
- Ce contrôle ne modifie ni données ni permissions.


## Contrôles fiscaux historiques — CI validée le 29 octobre 2026
- Commit `50d5560eec7eaea39d6adf80527d61f8b0339be2` : nouveau fichier `tests/test_facturation_ecart_historique.py` recensant explicitement les conventions fiscales historiques et vérifiant le projet SQL 013.
- Commit `883fb5b88b29b259610b9289aed3fd0c75677ee0` : test inclus dans le workflow lot C exécuté automatiquement sur `main`.
- Deux exécutions GitHub Actions sur ce SHA : `40906074056` et `40906074014` = `completed / success`.
- Les runs du commit précédent ont été annulés par concurrence, ils ne doivent pas être comptabilisés comme des échecs.
- Ce résultat CI **n'approuve pas juridiquement les taux historiques** et n'autorise pas l'activation de SQL 013 sans classification fiscale, tests SQL et concordance Python/SQL.


## Couverture TVA du catalogue — constat vérifié du 29 octobre 2026

- Production `wenydirqtmkywbxbxfal`, lecture seule : **7 SKU actifs** dans `public.sku_conditionnement` (`actif='OUI'`) et **0 classification** dans `public.erp_sku_fiscalite`.
- Le module `core/classification_fiscale.py` a été corrigé pour sélectionner la bonne version à date : une version future ou expirée ne bloque plus une version historique applicable ; des versions chevauchantes validées restent refusées. Commit `7478cbd5` et tests `89d81b17` ; assertion précisée en `d4514a76`.
- Nouveau module pur `core/audit_couverture_tva_sku.py` : détail par SKU préqualifié ou bloqué, sans requête ni mutation SQL et **sans jamais autoriser l'activation** de la facturation. Commits `0684caf1`, `da7e6472`, tests `f1ad31b9` ; workflow mis à jour par `c5f8542e`.
- CI GitHub Actions du SHA `c5f8542ed43742d39e46ef7e775c23f48d142297` : [40933174395](https://github.com/Verwolfy/erp-mortier/actions/runs/40933174395) et [40933174208](https://github.com/Verwolfy/erp-mortier/actions/runs/40933174208), **completed / success**. Le job du premier run confirme le succès des étapes « Tests du socle fiscal » et « Tous les tests ERP ».
- **Bloquant métier inchangé** : aucune affectation arbitraire de TVA aux 7 SKU. La RPC historique conserve des taux codés en dur ; le brouillon SQL 013 reste non activable. Les nouveaux modules sont des précontrôles, non un déploiement de conformité réglementaire.



## Registre opérationnel TVA des SKU — 29 octobre 2026

- Lecture seule Supabase PROD `wenydirqtmkywbxbxfal` : `public.sku_conditionnement` contient **7 SKU actifs** ; `public.erp_sku_fiscalite` reste à **0 classification**. La requête d'audit renvoie `QUALIFICATION_MANQUANTE` pour les 7 SKU.
- Générateur de registre de qualification **sans affectation automatique** : `core/registre_qualification_sku.py`, `scripts/generer_registre_qualification_sku.py`, tests `tests/test_registre_qualification_sku.py`. Commit CI `e0b66ea4b539d643487b4d3037995a2a3f888b7d` : deux workflows GitHub Actions `completed / success`.
- Nouveau script SQL de diagnostic **SELECT uniquement** `sql/audit_qualification_tva_sku_lecture_seule.sql`, commit `c7672f7f75700dfaf729fd4f83a6dea7cc8c019c`, exécuté en lecture seule sur production : 7 statuts `QUALIFICATION_MANQUANTE`. Deux workflows de ce commit : [40934496662](https://github.com/Verwolfy/erp-mortier/actions/runs/40934496662) et [40934496894](https://github.com/Verwolfy/erp-mortier/actions/runs/40934496894), `completed / success`.
- Le registre éditable des 7 SKU (identifiants, produits, formats et unités lus depuis la production, champs fiscaux vides) a été fourni en Markdown dans la conversation du projet ; il n'est pas enregistré dans le dépôt public.
- **Blocage maintenu :** les catégories TVA par SKU et le régime fiscal de l'entreprise doivent être validés sur preuves juridiques datées. Les règles de timbre et la concordance transactionnelle Python/SQL restent incomplètes ; ne pas activer la migration 013 ni inventer de taux.
- Aucun changement de schéma, de privilèges ou de données métier Supabase durant cette livraison.




## Migration 025 : attestations d'exonération TVA clients (29 octobre 2026)

- **Règle métier** : TVA normale **19 %** pour les ventes ; **0 %** uniquement en présence d'une attestation client applicable et documentée. Aucun taux réduit 9 % n'est proposé aux ventes. La règle métier est consignée dans `docs/REGLE_METIER_TVA_VENTES_19_OU_EXO_CLIENT.md`.
- Migration `sql/025_attestations_exoneration_client.sql` appliquée **sur TEST et sur PRODUCTION** via Supabase sous le nom `erp_025_attestations_exoneration_client`. Les deux historiques de migrations la confirment (TEST `20261029200111`, PROD `20261029200156`).
- Deux nouvelles tables vides en production : `public.erp_exonerations_tva_clients` et `public.erp_exonerations_tva_skus`. FKs vers `clients` et `sku_conditionnement`, contraintes de dates, de preuve et d'unicité ; aucune attribution d'attestation ou d'exonération.
- RLS activée pour les deux tables. Contrôle réel PROD : `anon` et `authenticated` sans droit SELECT ; `service_role` avec **SELECT uniquement**, sans INSERT/UPDATE/DELETE. Aucun accès de gestion UI ni aucune politique RLS permissive ne sont créés. L'avis Supabase `rls_enabled_no_policy` est intentionnel : les tables restent inaccessibles aux clients API ordinaires. Documentation : https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy
- Composant purement mémoire `core/lecture_exonerations_tva_clients.py` : reconstitue une attestation unique et sa portée SKU à partir de lignes lues par un futur service autorisé, refuse les doublons, certificats concurrents et statuts non validés. `core/exoneration_tva_client.py` conserve désormais les références du dossier et de la pièce interne dans les justificatifs de simulation.
- Tests ajoutés : `tests/test_exoneration_sql_025.py`, `tests/test_lecture_exonerations_tva_clients.py` ; intégrés au workflow `.github/workflows/lot_c_tests.yml`. Exécution SQL réelle et vérification ACL effectuées sur les deux projets, distinctes des tests CI.
- **Limites** : registres vides, 7 SKU actifs mais aucun dossier de classification TVA SKU ; aucune attestation client réelle validée ; pas d'interface administrative d'enregistrement ou validation ; pas de modification de `public.erp_sale_transaction` ; migration 013 toujours bloquée. Les pièces justificatives ne sont pas stockées : seule une référence interne est prévue. Ne pas activer la facturation à 0 % depuis la RPC historique.


## Migration 027 : circuit d'administration des exonérations — TEST et PRODUCTION (29 octobre 2026)

- La migration `sql/027_circuit_admin_exonerations.sql` est **appliquée sur Supabase TEST et PRODUCTION** ; migration enregistrée PROD sous `20261029202954 / erp_027_circuit_admin_exonerations`.
- Nouvelle RPC `public.erp_exoneration_tva_action` : `CREER_BROUILLON`, `VALIDER`, `REVOQUER`. L'opération reçoit un UUID de reprise et ne peut pas être rejouée avec un autre contenu. `SECURITY DEFINER` mais EXECUTE **révoqué** à `PUBLIC`, `anon`, `authenticated` ; uniquement le `service_role` serveur est autorisé. Le gestionnaire doit être vérifié dans `erp_security_authorities` + `users` actifs.
- Séparation des rôles : validation/révocation exigent **en plus** une présence active dans `erp_exonerations_tva_validateurs`, un validateur différent de `cree_par`, une vérification documentaire explicitement attestée et une référence d'avis. **Zéro validateur fiscal attribué en TEST ou en PROD : aucune validation n'est possible actuellement.** Ne pas peupler automatiquement cette table, l'identité du responsable fiscal et la preuve de son habilitation restent à établir.
- La table `erp_exonerations_tva_operations` journalise l'acteur métier, la requête, le type d'action et la référence du dossier ; aucune lecture ou écriture directe par les rôles API. Les tables `erp_exonerations_tva_operations` et `erp_exonerations_tva_validateurs` ont RLS activée et aucune politique permissive. Avis Info `rls_enabled_no_policy` attendu : https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy
- UI Administration : `modules/admin/views.py` expose, après contrôle `SECURITY_MANAGER`, un formulaire **de brouillon** de certificat ; il stocke l'UUID et le contenu de l'opération en session en cas de réponse réseau incertaine afin de permettre `Reprendre` avec la même opération. Aucune validation/révocation n'est activée dans l'interface.
- Service serveur : `modules/admin/exonerations_service.py` valide les champs et droits, appelle exclusivement l'action `CREER_BROUILLON` puis exige une réponse transactionnelle cohérente.
- TEST : transaction `BEGIN/ROLLBACK` avec création de brouillon fictif, rejeu idempotent, refus d'identité non autorisée et refus de validation sans valideur fiscal. **Aucune donnée fictive conservée.** Script réutilisable : `sql/027_smoke_test_rollback.sql`.
- PROD vérifiée par SELECT : 0 dossiers, 0 portées, 0 opérations, 0 validateurs ; exécution de RPC impossible pour `anon` et `authenticated`. Les 7 SKU actifs restent à qualifier ; la facturation SQL et la migration 013 demeurent inchangées et non homologuées.
- CI du commit `d1564eaf6fdb216a7d73145a088d840ca87226f8` : **deux workflows réussis** (`40949365562` et `40949365629`). Le déploiement Streamlit de cette version n'est toujours pas attesté ; Github `main` ne prouve pas la présence de l'écran hébergé.

**Suite recommandée :** identifier la vraie URL hébergée, valider les exigences juridiques réelles des exonérations, définir et habiliter le validateur fiscal séparé (action sensible), constituer les justificatifs de vrais clients, puis tester validation/révocation avec double contrôle avant d'ouvrir ce circuit dans l'interface. N'activer ni taux 0 % réel ni `erp_sale_transaction` tant que ces conditions ne sont pas réunies.


## Circuit de validation/révocation fiscale : test de bout en bout et migration 028 (29 octobre 2026)

- **TEST transactionnel contrôlé** sur Supabase `ffuhbmcfyexsbjwhryvj` : deux comptes actifs distincts ont simulé une préparation, validation et révocation d'attestation au moyen de la RPC 027. L'habilitation de manager et la désignation de contrôleur fiscal temporaires ont été ajoutées **à l'intérieur de `BEGIN ... ROLLBACK`**, avec des références documentaires explicitement fictives. Vérification après `ROLLBACK` : **0 attestation, 0 portée, 0 opération, 0 événement, 0 contrôleur fiscal**, et **1 manager initial** conservé. Aucun utilisateur réel n'a conservé de nouveaux droits.
- **Migration 028** : `sql/028_statut_habilitation_fiscale.sql` ajoute une RPC de lecture `erp_exoneration_tva_is_validator` qui exige à la fois compte actif, autorité `SECURITY_MANAGER` et habilitation fiscale active. `anon` et `authenticated` sans EXECUTE, `service_role` uniquement. Appliquée et contrôlée sur TEST d'abord. **Ne crée aucun validateur ni dossier**.
- **Service Administration** : `modules/admin/exonerations_service.py` exige une autorisation serveur fraîche avant toute validation/révocation, filtre les données de justification et vérifie la réponse de l'action SQL. Aucun droit de modification directe aux tables privées.
- **Interface Administration** : les actions `VALIDER` et `REVOQUER` ne sont visibles qu'après confirmation de la seconde habilitation fiscale ; elles présentent la référence du dossier, l'avis de vérification et la motivation. L'UUID d'opération est conservé dans la session pour une reprise idempotente après panne réseau. Le créateur de l'attestation ne peut pas valider son propre dossier (garde SQL).
- **Séparation juridique** : le métier n'autorise que 19 % normal ou 0 % sur attestation client validée. Aucun validateur fiscal n'est nommé automatiquement en production, aucun certificat fictif n'y est inséré, et la RPC de facturation historique est inchangée. La désignation réelle du contrôleur fiscal exige des preuves et une décision autorisée, non déductibles des rôles ERP.
- **Tests** : `tests/test_admin_exonerations_lecture.py` étendu (permissions et opérations), `tests/test_exoneration_sql_028.py` ajouté, workflow fiscal mis à jour.


## Migration 028 — contrôle fiscal double habilitation déployé en PRODUCTION (29 octobre 2026)

- Après validation des deux CI sur le commit `d2d99fccc4e389958ac39a628aace8f148156847` (runs `40951033928` et `40951033866` **completed/success**), `sql/028_statut_habilitation_fiscale.sql` a été appliquée sur **Supabase PRODUCTION** sous `erp_028_statut_habilitation_fiscale`, version `20261029204104`.
- Contrôle SQL production : `anon` **false**, `authenticated` **false**, `service_role` **true** pour EXECUTE de `erp_exoneration_tva_is_validator`. Toujours **0 validateur actif, 0 attestation, 0 portée, 0 opération et 0 événement**. Les 7 SKU restent actifs et 0 qualification fiscale est enregistrée.
- Tests sur TEST : cycle complet de préparation, double validation par second manager temporairement habilité, révocation, audit et rejouabilité idempotente ; **tout annulé par ROLLBACK**. Aucune habilitation ni donnée fictive persistante.
- Interface publiée sur `main` : `modules/admin/views.py`, onglet Administration → Exonérations TVA, affiche validation/révocation seulement si un second droit fiscal actif est confirmé par SQL ; l'écran exige vérification documentaire et justification, refuse la décision sur un dossier créé par le même utilisateur, et maintient l'UUID de reprise en cas de réponse réseau incertaine. Un repère visuel de version est affiché seulement aux managers autorisés : `SOF-ERP-20261029-EXO-028`.
- Cette interface n'est **pas confirmée déployée sur l'hébergement Streamlit**. Ne pas confondre GitHub `main`, succès CI et présence d'un écran dans l'application réellement consultée.
- **Aucune attribution automatique** d'habilitation fiscale : l'identité et la responsabilité du vrai valideur doivent être constatées avant de toucher au registre `erp_exonerations_tva_validateurs`. La facturation SQL historique reste à 19 % et ne traite pas encore le mécanisme client à 0 %.
