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
