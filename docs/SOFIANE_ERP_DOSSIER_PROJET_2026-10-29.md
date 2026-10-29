# SOFIANE ERP / ERP MORTIER — DOSSIER DE REPRISE

> Mise à jour : 29 octobre 2026 UTC. État fondé sur les lectures GitHub et Supabase, non sur une certification de déploiement. Ce dossier est une synthèse publiée sur `main`. Le dossier maître complet disponible dans la conversation du 29/10/2026 reste un instantané plus détaillé.

## Identité, objectifs et architecture
- Projet : Sofiane ERP / ERP Mortier, activité de mortiers, adjuvants, peinture.
- Dépôt principal : https://github.com/Verwolfy/erp-mortier ; branche `main`.
- Autre dépôt identifié : https://github.com/Verwolfy/ng-bs-erp (rôle à qualifier).
- Python 3.12 ; interface Streamlit ; PostgreSQL/Supabase ; Google Sheets pour des flux historiques ; fuseau métier `Africa/Algiers` ; pas de Docker.
- Domaines : authentification et droits, administration des référentiels, achats, matières et stocks, lots, production/OF, qualité, ventes/facturation, trésorerie et rapprochements, SCF, fiscalité algérienne, RH/paie, rapports et Guide & Aide.
- Référence de mission : `prompt_execution_autonome.md`. Autres documents annoncés : `prompt_fusion_main_erp.md`, `regles_algerie_erp.md`. Les consulter avant décisions réglementaires ou architecture détaillée.

## Environnements observés le 29 octobre 2026
| Environnement | Identifiant | État constaté |
|---|---|---|
| GitHub | `Verwolfy/erp-mortier`, `main` | accessible ; commits du 29/10 |
| Supabase production | `wenydirqtmkywbxbxfal` (`erp-mortier`) | ACTIVE_HEALTHY, eu-west-1 |
| Supabase test | `ffuhbmcfyexsbjwhryvj` (`erp-mortier-test`) | ACTIVE_HEALTHY, eu-west-1 |
| Streamlit déployé | inconnu | URL/commit servis à contrôler |
| Poste Windows local | inconnu | git status, stash et changements non poussés à contrôler |

## GitHub — point de reprise
- Dernier commit observé avant la publication du présent dossier : `0ffe8c078d879222b6b12860adb675c204eace54` (29/10/2026 14:00:45 UTC) ; correctif RH confirmant les droits avant écriture.
- Message de commit : « 1720 tests ERP verts ». **Déclaration de commit**, pas un nouveau lancement de pytest dans cette session.
- Commit `fdb7a09d449170a17a22441c54ba6bdda6b35d3e` : référentiels documentaires CNAS et migration 024 sur TEST/PRODUCTION, annoncés avec 1717 tests.
- Ancien `docs/ETAT_AVANCEMENT.md` contient des instantanés antérieurs (notamment 1547 tests) ; ne pas les prendre pour le chiffre courant.
- Réconciliation complète Git (branches divergentes, fichiers locaux, secrets historiques, tags et CI) **non démontrée** dans cette reprise.

## Supabase — état observé
- Production : migrations internes `erp_012` à `erp_024` incluses ; notamment :
  - 016 registre réglementaire ;
  - 017 SCF privé ;
  - 018 paie privée ;
  - 019 index SCF/paie ;
  - 020 reçus internes ;
  - 021 référentiels DGI/SCF ;
  - 022 qualification TVA SKU ;
  - 023 ACL lecture TVA SKU ;
  - 024 références documentaires CNAS.
- TEST : migrations internes 016 à 024 enregistrées avec versions d'horodatage distinctes.
- Les deux bases présentent les tables réglementaires, SCF, paie et reçus internes ; le scan d'inventaire des tables montre `rls_enabled=true` pour les tables `public` listées, **sans prouver que toutes les politiques sont correctes**.
- Production, nombres de lignes rapportés par l'outil d'inventaire : `parametres_reglementaires=5`, `regles_reglementaires=1`, `scf_plan_comptes=25`, `scf_exercices=0`, `scf_journaux=0`, `scf_pieces=0`, `scf_lignes=0`, `paie_periodes_v2=0`, `paie_bulletins_v2=0`, `paie_lignes_v2=0`, `erp_recus_internes=0`, `erp_sku_fiscalite=0`, `schema_migrations=0`.
- TEST : mêmes effectifs pour ces tables dans l'inventaire consulté.
- ATTENTION : les inventaires ne prouvent ni le statut juridique exact des paramètres, ni l'aptitude au calcul ; vérifier explicitement les enregistrements et les dates d'effet avant activation.
- Historique antérieur signalait 66 écarts de droits ACL TEST/PRODUCTION ; audit actuel des droits détaillés non refait. Ne pas répliquer les GRANT/RLS automatiquement.
- Ne pas confondre l'historique interne Supabase avec `public.schema_migrations`, table toujours vide dans l'inventaire.

## État des modules / risques
- Fonctionnalités existantes : achats, stocks, fabrication, ventes, finance, CRM, RH et tableaux de bord ; degré de couverture fonctionnelle à établir par scénarios E2E.
- Finance : rapprochements/encaissements ; reçus internes distincts des justificatifs fiscaux officiels ; contrôles pré-SCF de règlements `REGF-`.
- Facturation : présence historique de taux et règles de timbre codés en dur d'après l'audit antérieur (`modules/ventes/service.py`, `sql/005_atomic_sales.sql`). Vérifier si ces écarts subsistent sur le dernier `main` avant de conclure.
- Le simulateur fiscal dormant rejette un ancien calcul de timbre ; cela ne valide pas le circuit réel de facturation.
- TVA : références DGI de taux normal et réduit mentionnées dans les commits ; l'assujettissement de l'entreprise et la classification des SKU sont nécessaires, sans taux universel par défaut.
- SCF : 25 comptes de référence présents, mais pas de pièce/exercice/journal dans les décomptes observés ; aucune comptabilité opérationnelle certifiée.
- CNAS : taux documentaires signalés mais paie réglementaire non activée ; la validité temporelle et l'assiette restent à auditer.
- Données : des lignes existent sur production (ex. clients et factures) ; ne pas présumer qu'elles sont fictives.
- Déploiement : un push sur `main` ne prouve pas que l'application Streamlit visible a été déployée sur ce commit.

## Plan de réalisation
1. Étape 0 : tester droits/outils GitHub, Supabase, exécution locale/pytest et accès aux sources officielles.
2. Phase 0 : instantané des états, sans altérer les données.
3. Réconciliation : comparer toutes les branches, commits, migrations SQL dépôt, schémas et historiques de TEST/PRODUCTION. Versionner les écarts sans perte.
4. Phase 1 : contrôle de `correctif-db-service` si nécessaire.
5. Phase 2 : fusion compatible sur `main` avec tests.
6. Phase 3 : application compatible en production, contrôles et traçabilité.
7. Phase R : audit juridique du référentiel algérien et de ses dates d'effet.
8. Lot C : registres de paramètres réglementaires versionnés et `get_param(code,date)`; suppression des constantes réglementaires exécutables.
9. Lot D : SCF (exercices, comptes validés, journaux, pièces équilibrées et non modifiables).
10. Lot E : fiscalité, TVA/IFU/IBS/IRG, timbre et déclarations selon source fiable.
11. Lot F : RH/paie, CNAS et CASNOS avec assiettes et plafonds datés.
12. Lot G : reporting, rapprochements et conformité.
13. Lot H : Guide & Aide, documentation de chacune des opérations et incidents.

## Principes impératifs
- Paramètres légaux en base, versionnés, sourcés, datés, validés ; jamais de valeur devinée.
- Les états `a_confirmer` ou `projet` ne déclenchent aucun calcul ni dépôt.
- Absence de paramètre : erreur explicite et non valeur de secours.
- Montants en Decimal et opérations transactionnelles/idempotentes.
- Contrôles de non-régression, sécurité RLS/permissions, absence de secrets et audit des écritures équilibrées.
- Ne déclarer un test réussi que s'il est réellement exécuté ou si sa preuve est citée comme déclaration CI.
- Pas de sauvegarde PostgreSQL automatique : choix explicite du propriétaire mentionné dans le suivi.
- Arrêt avant destruction, changements RLS/GRANT/clefs, changement réglementaire majeur non validé, envoi externe ou coût.
- Une validation par expert-comptable algérien est requise avant un usage réglementaire de production.

## Prochaines actions non bloquées
1. Vérifier sur `main` les derniers tests et les chemins de documentation, puis synchroniser `docs/ETAT_AVANCEMENT.md` avec l'état factuel.
2. Faire des audits lecture seule des paramètres réglementaires, permissions, migrations, intégrité des schémas et des flux de facturation.
3. Inventorier les écarts GitHub non fusionnés et identifier le commit réellement exécuté par Streamlit.
4. Compléter les tests de parcours achats → stock, ventes → factures → règlements → écritures SCF ; ne pas activer des règles fiscales sans preuves réglementaires.

## Règle de mise à jour
À la fin de chaque lot : inscrire UTC, étape, succès/échec, liens commits/PR, tests réels, migrations TEST et PRODUCTION, tableaux comptés, sources juridiques, anomalies, décision et prochaine action. Réconcilier avec `docs/ETAT_AVANCEMENT.md` ; ne jamais écraser des éléments contradictoires sans les signaler.

## Prompt de reprise
« Reprends Sofiane ERP à partir de `docs/SOFIANE_ERP_DOSSIER_PROJET_2026-10-29.md` et `docs/ETAT_AVANCEMENT.md`. Vérifie en lecture seule GitHub `Verwolfy/erp-mortier/main` et les bases Supabase PRODUCTION `wenydirqtmkywbxbxfal` et TEST `ffuhbmcfyexsbjwhryvj`. Mets à jour l'état fondé sur des preuves et poursuis automatiquement les tâches compatibles, en demandant accord seulement aux points critiques. »

---
Dernière vérification documentaire : 2026-10-29 UTC.
