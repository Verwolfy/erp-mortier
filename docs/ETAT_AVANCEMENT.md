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
