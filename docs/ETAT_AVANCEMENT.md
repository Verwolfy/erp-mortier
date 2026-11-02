## 2 novembre 2026 — diagnostic écran IRG/CNAS

- Capture utilisateur : les trois indicateurs affichent « Non » au 02/11/2026.
- Contrôle SQL en lecture seule sur PRODUCTION : aucune ligne sous les codes `CNAS_SALARIE_TAUX`, `CNAS_EMPLOYEUR_TAUX`, `IRG_SALAIRES_MENSUEL` dans les registres respectifs. Le résultat correspond au comportement de `core/preflight_paie.py` ; la capture seule ne prouve pas la version hébergée.
- La [DGI présente les règles de traitement des salaires](https://www.mfdgi.gov.dz/fr/particuliers/irg-traitements-et-salaires) et diffuse une [table IRG 2022](https://www.mfdgi.gov.dz/images/bareme_irg/TABLE_IRG_2022.pdf). Ces sources sont des pistes documentaires ; leur applicabilité complète à la date et les paramètres CNAS doivent être vérifiés avant toute qualification.
- Aucun taux ou statut juridique ajouté ou modifié. La paie demeure non homologuée. Les simulations locales précédentes utilisent des valeurs explicitement fictives et ne valident pas ces paramètres.
- Le correctif précédent `ecbc174096c000d4bb28b59183f34bebdf6ed060` a réussi ses deux CI : [tests](https://github.com/Verwolfy/erp-mortier/actions/runs/41457688163), [audit](https://github.com/Verwolfy/erp-mortier/actions/runs/41457688076). Aucune écriture Supabase lors de ce diagnostic ; TEST non sollicité.
- Suite : constituer et recouper les sources officielles, dates d’effet, unités et règles de calcul, puis procéder aux tests et à la qualification réglementaire sans activer prématurément la paie réelle.

---

## 2 novembre 2026 — RH : retour incertain et congés fictifs visibles

- Les Actions du scénario `41058c1b03f1b91e4d58e8bc1dda400842b18213` sont réussies : [audit](https://github.com/Verwolfy/erp-mortier/actions/runs/41456800413), [tests](https://github.com/Verwolfy/erp-mortier/actions/runs/41456800460).
- Le registre signale désormais les demandes fictives `SIM-CNG-` qui figurent dans les compteurs.
- Les formulaires d’employé et de congé présentent un message de résultat non confirmé lors d’une erreur d’écriture et invitent à vérifier le registre avant une nouvelle tentative ; aucune exception technique n’est exposée. Il ne s’agit pas d’une reprise idempotente transactionnelle.
- Test AppTest avec écriture simulée incertaine : aucune exception à l’écran, aucun faux succès, avertissement visible, sans accès réseau ou écriture métier.
- Pas de modification Supabase, pas de changement des fiches/congés fictifs, aucun paiement ni permission modifiée ; TEST reste en pause. Le cycle d’approbation des congés et la paie homologuée restent à développer séparément.
- CI de ce changement à vérifier après publication.

---

## 2 novembre 2026 — scénario RH congés et paie simulée

- À la demande de l’utilisateur, trois demandes fictives `SIM-CNG-001` à `003` créées en PRODUCTION sur les employés SIM-RH-004, 006 et 008, marque `[SIMULATION]`, statut EN_ATTENTE ; insertion unique sans écrasement et relecture SQL. Aucune approbation, suppression ou modification des droits.
- Huit bulletins fictifs calculés hors ligne avec `preparer_bulletin_paie` ; taux et retenue arbitraires clairement étiquetés TEST_FICTIF, sans valeur fiscale, aucune preuve juridique prétendue. Aucun bulletin ni paiement enregistré en base. Scénarios et limites détaillés dans `docs/RH_SIMULATIONS.md`.
- Les trois congés apparaissent dans les compteurs de production. Les 10 employés fictifs et le projet TEST en pause sont conservés.
- Le cycle complet ne peut être revendiqué : approbation/annulation des congés et émission de bulletin homologuée restent à implémenter et auditer. Ne pas inventer de règle juridique.
- Tests ciblés : 28 réussis ; suite complète : 2 304 tests réussis. CI à vérifier après publication. Aucune transaction financière ni déclaration.

---

## 2 novembre 2026 — RH : lectures et validation des congés

- Lectures des employés et congés paginées et contrôlées ; panne ou refus affiché explicitement au lieu d’un registre faussement vide. Les formulaires restent bloqués si les lectures nécessaires échouent.
- Avant une demande, le service vérifie dates ISO, ordre des dates et employé existant actif, avec nouvelle lecture. Aucune règle de droit aux congés inventée. Cette vérification applicative n’est pas atomique : une modification concurrente reste possible avant insertion.
- Erreur de saisie ou de lecture : demande non confirmée, registre à vérifier avant nouvelle tentative. L’écriture hybride et sa reprise restent à auditer séparément.
- Tests isolés sur données fictives : employés inexistants/inactifs, dates invalides/inversées, panne et cas valide sans écriture réelle. Suite complète : **2 303 tests réussis**, dont un test regroupant six scénarios isolés. `git diff --check` réussi.
- Aucune écriture Supabase, aucun congé créé, aucun changement de permission ; les 10 employés fictifs existants sont conservés. TEST non sollicité.
- Suite : vérifier la CI et le rendu hébergé, puis sécuriser les écritures et la reprise incertaine ; la finalisation RH n’est pas encore acquise.

---

## 2 novembre 2026 — priorité RH et employés fictifs en production

### Autorisation et réalisation
- L’utilisateur demande explicitement de commencer par RH et d’ajouter des employés fictifs dans la base principale pour toutes les simulations du module. Cette autorisation porte sur ces fiches fictives, pas sur des transactions réelles, paiements, déclarations ou changements de droits.
- Schéma `public.employes` contrôlé : 8 colonnes texte, clé primaire employe_id, pas de trigger applicatif ; références entrantes demandes_conges et paie_bulletins_v2. Registre vide avant intervention.
- **10 employés fictifs insérés et relus en PRODUCTION** `wenydirqtmkywbxbxfal` : `SIM-RH-001` à `SIM-RH-010`, noms `[FICTIF]`, 8 actifs et 2 inactifs, six services, hiérarchie de managers valide. Une seule insertion, aucun écrasement de ligne existante.
- 0 congé et 0 bulletin v2 liés au jeu après insertion. Aucun compte utilisateur, salaire, transaction financière ou pièce juridique créé. Pas de synchronisation Sheets.
- PROD ACTIVE_HEALTHY ; TEST INACTIVE, non réveillé. RLS employes active après insertion ; aucun schéma ou droit changé.
- Fixture durable `tests/fixtures/rh_simulation_employes.json` et dossier `docs/RH_SIMULATIONS.md` : ID, scénarios, limites et priorités de finalisation. Le Dashboard inclut les 8 actifs fictifs ; avertissement ajouté au registre et guide complété.
- Correction RH : quand tous les employés sont inactifs, le formulaire de congé vide est remplacé par un message explicite ; aucun envoi possible depuis cette vue sans employé actif.

### Preuves
- **2 302 tests locaux réussis**. Tests du jeu : 10 identifiants uniques, 8 actifs, six services, managers valides, séquence réelle EMP inchangée.
- Streamlit AppTest réel : affichage de l’avertissement, seulement 8 employés sélectionnables, 009/010 exclus, zéro sélecteur/bouton de congé lorsque tous sont inactifs ; écritures interdites par doubles de test.
- Compilation et `git diff --check` réussis. Commit `7e35d902af43b96d304cb9029c79175909a93528` : [audit GitHub réussi](https://github.com/Verwolfy/erp-mortier/actions/runs/41454872814), [tests facturation et suite complète réussis](https://github.com/Verwolfy/erp-mortier/actions/runs/41454872781). Les 12 rubriques du guide rendent sans exception.
- Vérification SQL réelle limitée aux dix fiches et aux compteurs associés. Rendu hébergé toujours non attesté faute de session ERP connectée.

### Suite centrée sur RH
1. Lectures RH fiables et messages de panne ; contrôles des dates, employés actifs et références manager côté service.
2. Cycle complet des congés, reprises et permissions, avec ces mêmes identifiants de simulation.
3. Préparation paie uniquement sur paramètres vérifiés : aucune règle fiscale/sociale inventée ni paiement réel.
4. Ne pas annoncer le module finalisé avant ces contrôles ; ne pas supprimer/réinitialiser le jeu sans autorisation explicite.

---

## 2 novembre 2026 — Stocks, CRM et effectif RH (KPI-05)

### Réalisé
- Base `81fabbf1029d02acfbb363ebd27856904bfabe97`, historique et lot migrations préservés.
- Stocks : coûts requis pour les quantités positives ; coût/seuil/quantité invalide ou négatif = indisponibilité, jamais remplacement silencieux par zéro. Une quantité nulle reste valorisée à zéro sans inventer de coût. Seuils contrôlés par jointure conservant les lignes de stock ; référence absente ou ambiguë détectée. Même contrôle de seuils en Direction.
- Péremption : les lots déjà périmés et ceux expirant aujourd’hui restent visibles, quantité restante utilisée exclusivement. Lots détenus sans date signalés « risque non évalué » ; suppression du message global « Aucun risque ». Une date renseignée mais invalide bloque le calcul.
- CRM : les statuts réellement écrits par le formulaire (Nouveau, Contacté, En Négociation, Gagné, Perdu) sont reconnus, ainsi que les codes historiques du Dashboard. Probabilités hors 0–100 et valeurs invalides refusées. Une seule lecture du pipeline pour agrégats globaux et période.
- Le filtre CRM porte sur la date de création et le statut actuel : libellés explicités, « CA généré » remplacé par « valeur estimée des opportunités gagnées ». Pas de date de clôture inventée. Opportunités gagnées sans commercial conservées dans « Non attribué ».
- RH : utilisation du vrai champ `actif` (OUI/NON), au lieu de compter tous les employés faute de colonne `statut`. Services non renseignés visibles ; indicateur actif inconnu = indisponibilité.
- Guide intégré/Markdown actualisés ; repères `SOF-ERP-20261102-KPI-05` et `SOF-ERP-20261102-GUIDE-07`.

### Preuves
- **2 300 tests locaux réussis**, dont 29 nouveaux cas : statuts du formulaire/anciens codes, coût manquant, seuil inconnu, bornes de péremption, employé inactif, service manquant. Un avertissement gotrue préexistant.
- AppTest réel non vide Stocks/CRM/RH : effectif actif, pipeline pondéré et avertissement de date absente conformes aux données fictives locales ; aucune exception. Tests de panne/jeu vide existants réussis.
- Compilation et `git diff --check` réussis. Aucune donnée de production utilisée comme fixture.
- Commit `ab07bcac3d11a6430824df5bb16ec67b061c00ca` : [audit GitHub réussi](https://github.com/Verwolfy/erp-mortier/actions/runs/41452893530), [tests facturation et suite complète réussis](https://github.com/Verwolfy/erp-mortier/actions/runs/41452893360). Les 12 rubriques du guide rendent sans exception sous AppTest.
- Déploiement hébergé interne toujours non attesté faute de session connectée.
- Aucune transaction métier, migration, écriture Supabase, suppression ni modification de permissions. TEST non sollicité et conservé en pause.

### Limites et suite
1. Les seuils portent sur les lignes de stock présentes ; une référence sans ligne de stock n’est pas automatiquement assimilée à zéro. Une date de péremption absente n’est pas une preuve d’absence de péremption.
2. Vérifier les Actions et le repère KPI-05 dans une session autorisée.
3. Auditer le taux de rejet Production (retour anticipé sur période sans OF) puis les lectures historiques des modules métier, sans créer de transaction test réelle.
4. Poursuivre le rapprochement des migrations sur preuves, sans rejouer les candidats.

---

## 1 novembre 2026 — trésorerie indicative et retards Achats (KPI-04)

### Réalisé
- Reprise sur `237cc9a7cb0d4bad7df3341d12d8026b66459a43`, incluant le lot 13 migrations ; travaux concurrents conservés.
- Achats : suppression du retour anticipé qui ramenait tous les retards à zéro quand la période sélectionnée ne contenait aucune commande. Retards globaux sur EN_ATTENTE/PARTIELLEMENT_RECEPTIONNE, échéance strictement antérieure au jour courant ; réceptions complètes et annulations exclues. Date manquante ou statut inconnu = rubrique indisponible. Graphiques vides gérés sans jointure sur colonnes absentes.
- Finance/Direction : même calcul de trésorerie **indicative**, limité à Banque/Caisse : solde initial + encaissements VALIDE − décaissements VALIDE jusqu’au jour courant. Comptes tiers et règlements futurs exclus de ce solde ; aucun mouvement généré.
- Finance : flux et taux de lettrage restent filtrés par la période choisie, sur les règlements validés. Montants absents, allocations négatives/supérieures au total, dates invalides et comptes de règlement inconnus provoquent une indisponibilité. Les soldes restent globaux même si la période des flux est vide.
- Graphique identifié par ID + nom du compte pour distinguer les homonymes. Guide et légendes explicitent les limites : soldes initiaux non datés, autres écritures non prises en compte, pas de rapprochement bancaire ni de solde comptable historique.
- Repères : `SOF-ERP-20261101-KPI-04`, `SOF-ERP-20261101-GUIDE-06`.

### Preuves
- **2 271 tests locaux réussis**, dont 19 nouveaux cas ciblés ; un avertissement gotrue préexistant. Aucun accès serveur depuis ces tests.
- Streamlit AppTest : Dashboards vides et pannes isolées, 12 rubriques du guide sans exception. Compilation et `git diff --check` réussis.
- Références métier : création/réception des commandes dans SQL 004 ; comptes Banque/Caisse et flux validés dans SQL 006. Aucun barème ou traitement fiscal inventé.
- Commit `a88d3643642db4215bc82b23ff6bf5f2ccd2a450` : [audit GitHub réussi](https://github.com/Verwolfy/erp-mortier/actions/runs/41327161225) et [tests facturation/suite complète réussis](https://github.com/Verwolfy/erp-mortier/actions/runs/41327161202).
- AppTest supplémentaire avec jeu non vide fictif : trésorerie Direction et rendu Finance sans exception, solde attendu vérifié.
- Déploiement Streamlit interne non attesté : dernière observation sur l’écran de connexion.
- Aucune écriture Supabase, migration, suppression, transaction métier ou modification de permissions. TEST non sollicité, conservé en pause.

### Suite
1. Contrôler les Actions puis les repères dans une session ERP autorisée.
2. Auditer les valeurs de stock manquantes et les agrégats CRM/RH ; étendre les lectures contrôlées aux modules historiques.
3. Poursuivre le rapprochement des migrations sur preuves, sans réexécuter les candidats ni modifier les habilitations.

---

## 1 novembre 2026 — Lot 13 : dossier de rapprochement des migrations Supabase (sans mutation)

### Réalisé
- PR [#38](https://github.com/Verwolfy/erp-mortier/pull/38) fusionnée dans `main` au commit `2f35e243fc410e49bcd8ca4c99d278c871b1b73d`. Les deux CI de PR réussies : [audit complet](https://github.com/Verwolfy/erp-mortier/actions/runs/41326198104), [facturation](https://github.com/Verwolfy/erp-mortier/actions/runs/41326198126). Les CI du merge ont été déclenchées et sont à confirmer séparément.
- Nouveau `docs/migration_evidence_20261101.json` : 23 versions natives observées (21 ERP et 2 NextGen) et leurs sources locales **possibles** ; classement archives déclarées / candidats non vérifiés / brouillons thématiques / propositions non exécutées.
- Nouveau `scripts/auditer_preuves_migrations.py` : vérification hors ligne des fichiers candidats et calcul de leurs SHA-256 **locaux uniquement**, sans client réseau ni accès SQL ; rejet des chemins dangereux et des métadonnées invalides.
- Tests `tests/test_auditer_preuves_migrations.py` ; note d'exploitation `docs/LOT13_AUDIT_PREUVES_MIGRATIONS.md`.

### Supabase production, lecture seule
- `supabase_migrations.schema_migrations` : **23** versions ; `public.schema_migrations` : **0** entrée. Ne pas combler ce registre avec les empreintes de scripts seulement *candidats*.
- Conseil sécurité Supabase : **86 alertes INFO `rls_enabled_no_policy`**, aucune autre famille dans la réponse reçue. RLS activée et droits SELECT refusés aux rôles `anon`/`authenticated` sur `produits`, `erp_sku_fiscalite`, `site_produits`, `site_demandes`. Pas de changement de permission.
- Archives SQL du 27/10 historiquement déclarées appliquées, sans preuve de correspondance du SHA-256 aux instructions réellement transmises ; les versions 016–032 n'ont que des candidats documentaires, les deux SQL site sont des **propositions non exécutées**.
- **Aucune modification SQL**, aucune clé copiée, aucun script rejoué, aucune activation web ou collecte.

### Suite
1. Confirmer les CI du commit de fusion puis la version effectivement déployée sur Streamlit via un compte autorisé (vérification anonyme impossible depuis cette session réseau).
2. Pour chaque version native, demander une preuve indépendamment vérifiable du contenu SQL réellement exécuté / des objets ; ne jamais conclure sur une similitude de nom.
3. Sécuriser et réunir les pièces techniques, prix et dossiers fiscaux NextGen avant toute qualification, sans valeurs fictives.
4. Conserver le lancement Cloudflare et la collecte au statut NO-GO jusqu'aux validations d'accès et juridiques.

---

## 1 novembre 2026 — périodes de paie et décaissements OPEX (KPI-03)

### Correction réalisée
- Base `5778fbe8773b316156c8f843a51a54f1cf9dc839`, suites NextGen et KPI-02 conservées.
- Le P&L additionnait les fiches de paie de toutes les périodes : filtrage désormais par `mois` ET `annee`. Des fiches dans une sélection de mois partiels rendent la rubrique indisponible ; aucun prorata journalier n'est déduit de données mensuelles.
- Le montant reste explicitement un **net enregistré, tous statuts de paiement**, pas un coût employeur, une preuve de validation ni un paiement confirmé. Aucune règle fiscale, sociale ou de validation de paie ajoutée.
- OPEX : seuls les décaissements `VALIDE` classés via la catégorie fournisseur contenant OPEX sont retenus (convention existante). Brouillons/annulations exclus. La jointure ne masque plus un fournisseur absent ; catégorie vide, référence ambiguë, montant invalide/négatif et statut inconnu sont signalés comme indisponibles.
- Guide et cascade de coûts précisent que le solde mélange facturation et décaissements. Les limites des coûts historiques, avoirs, cotisations employeur et validation de paie restent ouvertes.
- Repères visibles : `SOF-ERP-20261101-KPI-03`, `SOF-ERP-20261101-GUIDE-05`.

### Preuves
- **2 237 tests locaux réussis**, dont 29 nouveaux cas : changement d'année, février bissextile, périodes partielles, montants absents, fournisseur inconnu/doublonné, paiements annulés, intégration au P&L. Un avertissement gotrue préexistant.
- Rendu Streamlit AppTest du Dashboard vide et des pannes de lecture réussi ; compilation et `git diff --check` réussis.
- Tests exclusivement locaux, aucun accès de test à Supabase. Aucune transaction métier, migration, suppression ou modification des droits. TEST non sollicité, reste en pause.
- Commit `6461fe7679c4406bf5ce76d05e8cba02c4fbf103` : [audit GitHub réussi](https://github.com/Verwolfy/erp-mortier/actions/runs/41326237528). [Workflow facturation](https://github.com/Verwolfy/erp-mortier/actions/runs/41326237661) marqué cancelled après une mise à jour concurrente de main, mais toutes ses étapes (socle fiscal, suite complète, compilation et post-traitements) sont success. Les relances suivantes ont aussi été annulées par des mises à jour concurrentes : ne pas présenter ces runs comme verts.
- AppTest supplémentaire : mois partiel = P&L indisponible sans bloquer RH ; mois complet = calcul attendu. Les 12 rubriques du guide rendent sans exception.
- Dernier constat hébergé : écran de connexion ; version interne non attestée.

### Prochaines actions
1. Contrôler les Actions et vérifier KPI-03 après authentification dans l'ERP.
2. Auditer les soldes par compte dans Finance (le graphique actuel ne montre que les soldes initiaux) et les retards Achats sur période vide.
3. Poursuivre l'inventaire des migrations en lecture seule ; aucune régularisation automatique sans preuve de correspondance.

---

## 1 novembre 2026 — indicateurs de facturation et créances (KPI-02)

### Réalisé
- Reprise sur `2fce4e1407fe97b872347b81f1c043421b827b4f` ; lots NextGen 10–12 et leur documentation conservés.
- Direction, Ventes et P&L : facturation brute des seules `FactureClient` au statut `VALIDE`. Brouillons/annulations exclus ; avoirs validés suivis séparément. Les libellés disent explicitement « facturation brute », sans prétendre calculer un CA net comptable.
- Balance âgée globale conservée quand la période de vente est vide. Paiements partiels déduits ; factures soldées exclues. Retards calculés en jours calendaires (bornes 30/31 et 60/61 testées).
- Statuts inconnus, montants invalides/non finis et échéances manquantes des créances ouvertes provoquent une indisponibilité, jamais un faux zéro. Règles documentaires fondées sur les RPC Ventes/Finance existantes, sans nouvelle règle fiscale.
- P&L : mêmes factures pour revenus et lignes de coûts ; coût manquant/ambigu et facture sans lignes refusés. Le solde est renommé « solde de gestion estimatif » et les limites sont affichées : coûts actuels non historiques, salaires non filtrés par période. OPEX et paie restent à auditer.
- Guide intégré et guide Markdown complétés ; correction de l'ancienne FAQ PARTIELLE : le lettrage conserve `VALIDE`, le solde distingue paiement partiel/complet.
- Repères : `SOF-ERP-20261101-KPI-02` et `SOF-ERP-20261101-GUIDE-04`.

### Preuves
- **2 208 tests locaux réussis**, dont 29 nouveaux cas de calcul/rendu ; un avertissement de dépréciation gotrue préexistant.
- Tests Streamlit AppTest réels en processus isolés : panne de lecture sans faux chiffre et jeu vide sans exception. Données fictives exclusivement locales ; aucun accès serveur pendant les tests.
- `pip check`, compilation des modules modifiés et `git diff --check` réussis.
- Commit publié : `9914b0dcf78da302ebe1f11f090b12c950ef46df`. Actions réussies : [tests facturation et suite ERP](https://github.com/Verwolfy/erp-mortier/actions/runs/41325741166), [audit de réconciliation et suite ERP](https://github.com/Verwolfy/erp-mortier/actions/runs/41325741288).
- Les 12 rubriques du guide rendent sans exception sous Streamlit AppTest. Nouvelle ouverture du site hébergé : écran de connexion ERP, déploiement des écrans internes non attesté.
- Aucune écriture Supabase, transaction métier, migration, suppression ou modification de permissions. Projet TEST non sollicité, conservé en pause.

### Suite
1. Vérifier les Actions du commit puis le repère KPI-02 dans une session ERP authentifiée.
2. Auditer séparément les périodes de paie, les OPEX, les avoirs/compensations et les coûts historiques avant toute interprétation comptable du P&L.
3. Étendre les lectures contrôlées aux modules historiques et poursuivre l'inventaire des migrations sans rejeu automatique.

---

## 1 novembre 2026 — Lot 12 : inventaire NextGen paginé sans faux complet

### Résultat
- **Défaut réel corrigé** : le diagnostic des SKU reposait sur une seule requête PostgREST `range(0,limite)` et pouvait accepter une réponse plafonnée par l'API comme inventaire complet.
- PR [#37](https://github.com/Verwolfy/erp-mortier/pull/37) fusionnée sur `main` : commit `6dfbf7005bb2f4196f9ccfe20950706a587eb6f6`.
- `modules/admin/nextgen_readiness_service.py` : pages ordonnées de 100 lignes demandées, `count=exact`, offsets progressifs sur les lignes effectivement reçues, comparaison des totaux entre pages, contrôle des doublons et limites des quatre tables, révérification `SECURITY_MANAGER` avant toute page.
- Clés SQL respectées : `pf_id`, `sku_id`, `mp_id` et, pour `erp_sku_fiscalite`, la clé **composée `sku_id, date_effet`**.
- `tests/test_nextgen_readiness.py` : nouvelles vérifications des plafonds API (142 SKU, pages limitées à 17), compte exact absent ou variable, page intermédiaire vide, dates fiscales distinctes, doublons, révocation de permission. Documentation `docs/LOT12_NEXTGEN_LECTURES_EXHAUSTIVES.md` et guide actualisés.
- GitHub CI vérifiées **sur la PR et sur `main` fusionné** : [audit complet réussi](https://github.com/Verwolfy/erp-mortier/actions/runs/41325282927), [tests lot C réussis](https://github.com/Verwolfy/erp-mortier/actions/runs/41325283076). Aucun échec sur ces deux runs.

### Lecture Supabase PRODUCTION
- Contrôles inoffensifs du 01/11/2026 : 50 produits actifs, 142 SKU actifs, 119 matières premières, zéro dossier `erp_sku_fiscalite` ; clés primaires vérifiées dans `pg_constraint`.
- Aucun SQL de modification, aucun RLS/GRANT, aucune création de données, aucun déploiement Cloudflare.
- Les volumes inférieurs aux limites du service ne garantissent pas la disponibilité du réseau ni un snapshot transactionnel intertables.

### Suite
1. Vérifier après authentification que l'ERP Streamlit hébergé utilise bien un commit contenant ce correctif ; sans accès à la session, la CI ne prouve pas le déploiement.
2. Recueillir les preuves réelles (tarifs, documents fiscaux, densités, compositions de kits) pour les SKU NextGen ; ne jamais convertir `NON_VERIFIE` en homologation automatique.
3. Continuer l'audit de correspondance des 23 migrations natives Supabase, sans rejeu ni modification des ACL.
4. Préproduction du site toujours NO-GO sans protection Cloudflare Access et validation juridique.

---

## 1 novembre 2026 — Lot 11 : export contrôlé du suivi NextGen et audit migrations

### Réalisé
- PR [#36](https://github.com/Verwolfy/erp-mortier/pull/36) fusionnée sur `main` par merge non destructif ; commit `81a0ebc68ebb220ed75b45635381d28919cfce68`.
- Ajout du générateur CSV `exporter_registre_nextgen_csv` et du bouton réservé au `SECURITY_MANAGER`. Le service revalide l'habilitation ; liste à cinq champs métier, deux colonnes de suivi sans preuve préremplie et statut `NON_VERIFIE`. Rejet des lignes invalides, des autorisations implicites et des formules de tableur.
- Tests NextGen étendus et `docs/LOT11_NEXTGEN_EXPORT_SUIVI.md` + `docs/guide_utilisateur.md` actualisés. Aucun CSV privé ni tarif n'a été committé.
- GitHub Actions **sur la branche PR** : [suite complète + réconciliation réussies](https://github.com/Verwolfy/erp-mortier/pull/36). Les deux vérifications du merge `81a0ebc` restent à contrôler séparément au moment de cette entrée.

### Audit Supabase en lecture seule
- PRODUCTION : 23 versions dans `supabase_migrations.schema_migrations` (**21 ERP + 2 site**), tandis que `public.schema_migrations` contient 0 ligne. L'historique SQL natif n'est pas vide.
- Racine `sql/` de l'ERP : 48 entrées dont scripts de préflight, rollback, brouillons et répertoires. `sql/supabase_applied/` contient des sources historiques ; il faut prouver correspondances de contenu et empreintes avant toute régularisation.
- Catalogue privé site : 50 produits ; vue publiable : zéro ; demandes : zéro. Qualification NextGen : 142 SKU actifs, 142 sans tarif et dossier fiscal, 7 kits, 48 liquides sans conversion, `PROOF-PU-SEAL` sans SKU.
- **Aucune DDL ou écriture de données**, aucune RLS/GRANT modifiée, aucun secret, aucune publication de produit ou collecte activée. Projet TEST inactif.

### Suite
1. Confirmer les CI du merge puis observer le commit réellement déployé dans Streamlit après connexion.
2. Qualifier les SKU sur pièces source dans le circuit interne ; le CSV ne donne aucun droit de fabriquer/facturer/publier.
3. Reconstituer le catalogue de migrations par preuve de contenu et comportement, sans rejouer les brouillons.
4. Site Cloudflare : aucune activation avant protection Access et revue juridique distinctes.

---

## 1 novembre 2026 — lectures fiables CRM/Dashboards et rendu graphique

### Problème corrigé
Les lectures historiques retournaient une liste vide sur panne Supabase et
pouvaient être tronquées par la limite de l'API. CRM affichait alors un registre
vide ; les Dashboards pouvaient calculer un zéro ou un agrégat partiel.

### Intervention
- Nouveau `core/strict_reads.py` : SELECT uniquement, tri par clé, pagination,
  total exact vérifié à chaque page, contrôle des doublons et des pages incomplètes.
  Une limite API inférieure aux 500 lignes demandées ne coupe plus la lecture.
  Borne de consultation par défaut : 10 000 lignes ; dépassement = indisponibilité,
  jamais un total partiel. Les filtres de dates sont conservés sur chaque page.
- Contrôle des permissions serveur à chaque page et projections privées inchangés.
  Aucun cache partagé, aucun élargissement de droits, aucune donnée serveur brute
  dans les messages d'erreur. La pagination ne garantit pas un snapshot atomique
  de toutes les tables : les modifications concurrentes à cardinalité constante
  restent une limite connue.
- CRM : pipeline, historique, clients et liste de types d'interactions utilisent
  les lectures contrôlées. La boîte NextGen ajoutée dans les commits intervenus
  depuis le 31/10 est préservée, avec ses drapeaux et restrictions.
- Dashboards : les neuf rubriques isolent les erreurs de lecture ; une rubrique
  indisponible ne coupe plus les suivantes. Les calculs métier ne sont pas changés.
  Repère visible CRM/Dashboards : `SOF-ERP-20261101-READ-01`.
- Guide complété sur indisponibilité, limites et pagination ; repère
  `SOF-ERP-20261101-GUIDE-03`.
- Installation neuve : panne de rendu reproduite avec PyArrow 26.0.0 et
  NumPy 1.26.4 imposé par pandas 2.2.0. `requirements.txt` fixe désormais
  PyArrow 25.0.1 ; import et conversion DataFrame → Arrow vérifiés.
  Aucun changement de version de pandas, Supabase ou NumPy dans le dépôt.

### Preuves
- Base de travail : `bed365faea612c773d134b3e20b422fef363b44d`, changements
  distants conservés. Aucun fichier du poste Windows modifié.
- **2 143 tests locaux réussis**, dont 36 nouveaux cas : 1 203 lignes avec une
  limite API de 200, erreur sur deuxième page, total variable/absent, clés
  dupliquées, permission retirée entre pages, projections privées et dates.
- Deux tests de rendu avec le vrai moteur Streamlit AppTest : panne Ventes =
  trois rubriques indisponibles sans faux CA à zéro ; RH/Stocks restent rendus.
  Pannes CRM = messages explicites, aucun faux succès ni registre vide annoncé.
  Aucun accès Supabase ou Sheets dans ces tests.
- `pip check`, compilation et `git diff --check` réussis. Python 3.12 local ;
  Python 3.11 de la CI reste à contrôler après publication.
- Lecture SQL production : pipeline 0, interactions 0, factures 1 avec une clé
  unique. PROD ACTIVE_HEALTHY ; TEST INACTIVE, non interrogé et non réactivé.
- Navigateur : l'ERP affiche son écran de connexion ; la session du 31/10 n'est
  plus disponible. Le nouveau code n'est pas encore attesté dans l'hébergement.

### Suite et limites
1. Vérifier les CI du commit puis le repère READ-01 dans une session ERP connectée.
2. Étendre progressivement ces lectures aux autres modules ; les fonctions
   historiques de db_service restent inchangées pour éviter une rupture globale.
3. Auditer les statuts de factures, les coûts manquants et les agrégats P&L :
   la fiabilité du transport ne constitue pas une validation comptable/fiscale.
4. Les lectures bornées peuvent refuser un référentiel >10 000 lignes ; prévoir
   des agrégats SQL autorisés ou des filtres supplémentaires si le volume l'exige.

**Aucune écriture métier, migration SQL, suppression ou modification de permissions.
TEST reste en pause.**

---

## 31 octobre 2026 — parcours hébergé après connexion sécurisée

Cette entrée complète l'audit ci-dessous : le blocage de connexion a été levé
pendant la même intervention. Compte affiché ADMIN, sans modification des droits.
Les identifiants ont été saisis via le formulaire sécurisé, sans exposition.

| Module | Consultation effectivement vérifiée |
|---|---|
| Administration | Écran Clients et tableau des 7 clients existants |
| Achats | Nouvelle Commande puis Historique & Suivi ; aucune commande/réception |
| Stocks | État des Stocks, onglet matières premières en vrac et tableau rendu |
| Production | Production et CQ ; aucun OF actif (SQL : 1 OF TERMINE) |
| Ventes | Brouillon affiché sans soumission, avertissement fiscal présent ; Suivi factures : 1 facture existante |
| Finance | Tableau de bord : aucun règlement ; navigation des onglets visible |
| RH | Registre des Employés : aucun employé ; onglets conditionnels affichés |
| CRM | Pipeline sans opportunité et Historique des échanges vide |
| Dashboards | Les 9 onglets ouverts : Direction, P&L, Ventes, Achats, Stocks, Production, CRM, RH et Finance |

- Aucune erreur applicative visible dans ce parcours. Il s'agit d'un contrôle
  de consultation ADMIN, pas d'un test exhaustif des formulaires, des autres
  profils ni des transactions de bout en bout.
- Recoupement SQL en lecture seule : clients 7, factures 1, commandes achats 0,
  réceptions 0, employés 0, règlements 0, opportunités 0, interactions 0,
  OF 1 (TERMINE), lignes de stock MP 3.
- Le CA HT affiché dans Direction et Ventes correspond au montant de la facture
  consultée. Les autres calculs de marge, valorisation et fiscalité ne sont pas
  certifiés par ce constat.
- **Écart de déploiement :** le guide hébergé affiche encore les 9 anciennes
  rubriques et le texte « Sauvegarde automatique », sans repère
  SOF-ERP-20261031-GUIDE-02. Le nouveau guide n'est donc pas attesté dans cette
  session. La page Ventes affiche SOF-ERP-20261030-EXO-HIST-02.
  Ne pas annoncer les corrections comme déployées sur Streamlit.
- Correctif publié sur main : `35ea5e16556efeaf5d7ee779b75efdceb9969a01`.
  **Deux CI completed/success** : audit
  https://github.com/Verwolfy/erp-mortier/actions/runs/41224305921
  et lot C https://github.com/Verwolfy/erp-mortier/actions/runs/41224305908.
- **Prochaine action :** vérifier la source/branche et la mise à jour du
  déploiement Streamlit, puis contrôler le nouveau repère ; traiter ensuite
  les lectures historiques non paginées et les erreurs converties en listes
  vides avec tests de non-régression. TEST reste en pause.
- Aucun bouton de validation métier utilisé ; aucune écriture SQL ou changement
  de permissions. Les opérations normales d'authentification restent distinctes
  des transactions métier interdites pour les tests.

---

## 31 octobre 2026 — audit autonome, aide et activité Dashboards

**Consigne prioritaire : TEST doit rester en pause et ne doit pas être supprimé.**
Cette instruction remplace toutes les anciennes propositions de suppression ou
réactivation de TEST présentes dans l'historique ci-dessous.

### Actions réalisées
- Lecture initiale de ce journal sur `main` (`b199f7507f66ef95b108838b0360bbd134c88c5a`).
- Application `https://nextgent-erp.streamlit.app/` ouverte : écran Connexion ERP
  rendu, champs login/mot de passe et bouton Se connecter. Aucune session connectée.
  Les neuf écrans internes **ne sont pas validés sur l'hébergement** ; connexion
  utilisateur nécessaire, sans récupération de secrets en base ni contournement.
- Correction des 12 filtres de dates et du curseur de péremption Dashboards :
  signal d'activité envoyé au contrôleur existant. Aucun renouvellement direct
  de `last_activity`, aucune modification des droits ou de la durée de session.
- Guide & Aide réécrit à partir des écrans du dépôt : 12 rubriques, ajout RH,
  Dashboards et incidents/reprise ; correction du parcours Ventes, de Finance,
  des entrées de stocks (positives, MP/emballages) et de la confusion entre
  enregistrement et sauvegarde. Repère `SOF-ERP-20261031-GUIDE-02`.

### Preuves et limites
- Suite locale avant correctif Dashboards : **2 074 tests réussis** ; test ajouté
  couvrant les 13 filtres. **Suite finale : 2 075 tests réussis**, compilation et
  `git diff --check` réussis. Navigation locale Streamlit AppTest des **12 rubriques**
  du guide : aucune exception. Ce test local ne prouve pas le déploiement hébergé.
- CI de départ : audit `41223175642` et lot C `41223175689`, tous deux success.
- Supabase : PROD `wenydirqtmkywbxbxfal` ACTIVE_HEALTHY ; TEST
  `ffuhbmcfyexsbjwhryvj` INACTIVE. Aucune requête adressée à la base TEST.
- Schéma PROD : **88 tables public, 88 avec RLS active**. Les colonnes déclarées
  pour **54 tables de SCHEMA_CONFIG** existent toutes. Cela ne valide pas les
  types, les projections de tous les appels ni les droits de chaque utilisateur.
- Historique Supabase : **21 migrations enregistrées**, dont 031 et 032.
  Trigger `erp_factures_garde_exonerations` présent et actif (`tgenabled=O`).
  La numérotation historique Supabase 012–018 ne correspond pas nécessairement
  aux fichiers SQL du même numéro : ne pas rejouer sur la seule base du numéro.
- Conseiller sécurité : 84 avis INFO RLS sans politique ; aucun WARN/ERROR remonté.
  Ces tables privées ne doivent pas recevoir de politiques permissives pour
  effacer l'avis. Voir https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy
- Performance : 15 clés étrangères sans index couvrant et 8 index non utilisés
  signalés INFO. Aucune suppression d'index ni DDL automatique. Voir
  https://supabase.com/docs/guides/database/database-linter?lint=0001_unindexed_foreign_keys
- Logs : inventaire sur la fenêtre par défaut de 24 h (232 edge, 13 postgres,
  1 pgbouncer). Les champs level/status_code interrogés sont vides : **aucune
  conclusion d'absence d'erreurs** ne peut être tirée de cet inventaire.

### Anomalies et travaux restant ouverts
1. Tester Administration, Achats, Stocks, Production, Ventes, Finance, RH, CRM,
   Dashboards avec une session utilisateur autorisée, en consultation uniquement.
2. `core/db_service.fetch_data`, `fetch_data_filtered` et
   `fetch_data_by_date_range` renvoient `[]` sur erreur et ne paginent pas.
   Les Dashboards/CRM utilisent encore ces chemins : risque de faux zéros ou
   d'agrégats tronqués. Préparer une migration ciblée vers lectures strictes,
   avec tests de panne, volumétrie et affichage indisponible avant généralisation.
3. Les KPI Direction incluent des brouillons dans les impayés et n'excluent pas
   explicitement tous les statuts non comptabilisés du CA : définir et tester
   les statuts métier admissibles avant correction du calcul.
4. Homologation TVA/exonérations, SCF et paie encore incomplète ; aucune donnée,
   pièce justificative, classification ou habilitation fiscale inventée.
5. Contrôler la CI du nouveau commit puis le repère du guide en ligne.

**Aucune transaction métier, migration, suppression, modification de permissions
ou de contrôles de sécurité exécutée.**

---

## 31 octobre 2026 — qualification documentaire des SKU, sans taux fictifs

- **Contrôle PRODUCTION en lecture seule** : `public.sku_conditionnement` contient 7 SKU actifs (SKU-001 à SKU-007), `public.erp_sku_fiscalite` est vide (0 classification). Les formats et unités réels ont été transcrits dans `docs/QUALIFICATION_SKU_PRODUCTION_20261031.md`.
- Nouveau service privé `modules/admin/qualification_sku_service.py` : deux lectures Supabase, garde `require_security_manager()`, contrôle de pagination et d'intégrité des données, inventaire par SKU. Aucune qualification, taux ou validation attribué automatiquement.
- Onglet Administration `📋 Qualification TVA SKU` : affiche les références actives, le nombre de dossiers documentaires et permet d'exporter un registre Markdown lorsque le tableau fiscal est vide. Repère visuel `SOF-ERP-20261031-SKU-REVUE-01`. **L'hébergement Streamlit n'est toujours pas vérifié.**
- Les tests `tests/test_qualification_sku_service.py` couvrent refus d'accès, catalogue incohérent, panne réseau et absence d'activation fiscale ; ajoutés à la CI du lot C.
- **Aucune migration SQL ni écriture dans Supabase**, car le besoin est une revue du catalogue, pas une modification du droit fiscal. Les migrations 031/032 restent en production et la facturation 0 % non activée. Ne pas créer de pièces, taux ou validateurs fictifs.
- Exploitation : GitHub `main` uniquement et Supabase PRODUCTION `wenydirqtmkywbxbxfal` uniquement. L'ancienne base TEST est inactivée mais non supprimée physiquement.

---

## ⚠️ Politique opérationnelle prioritaire — 30 octobre 2026

**État vérifié :** `Verwolfy/erp-mortier` ne conserve que la branche `main` après suppression de **31 branches secondaires**. Le nettoyage GitHub a réussi via un workflow ponctuel, immédiatement retiré du dépôt après exécution.

**PRODUCTION unique :** Supabase `erp-mortier`, projet `wenydirqtmkywbxbxfal`, reste actif. L'ancien projet `erp-mortier-test`, `ffuhbmcfyexsbjwhryvj`, a été **mis en pause et constaté INACTIVE**, mais **n'est pas encore supprimé définitivement** : l'outil Supabase connecté ne dispose pas de la commande de suppression de projet. Consigne remplacée le 31/10/2026 : conserver TEST en pause, sans suppression ni réactivation.

**Consignes pour les prochains tours :** travailler directement sur `main` et la BDD de production, sans nouvelle branche ni passage par la base de test. Vérifier les CI, le SQL, l'identité du projet et les permissions avant et après chaque opération. Ne pas inventer de justificatifs fiscaux ni activer les transactions 0 % sans homologation. La documentation détaillée est `docs/EXPLOITATION_UNIQUE_MAIN_PRODUCTION.md`.

---

## 30 octobre 2026 — migration 031 appliquée directement sur PRODUCTION (état actuel, prioritaire)

**Décision de l'exploitant :** pour les prochaines migrations sûres, travailler directement sur les scripts GitHub `main` et sur **Supabase PRODUCTION** (`wenydirqtmkywbxbxfal`), sans faire de la base TEST une étape obligatoire. Appliquer les contrôles de prévol, CI, permissions et validation post-déploiement directement sur PRODUCTION, sans données d'essai fictives ni contournement des gardes de sécurité. Demander une validation préalable uniquement pour les opérations critiques/destructrices. L'exploitant ne demande pas de sauvegarde PostgreSQL.

**Migration 031 effectivement installée :** `sql/031_precontrole_exoneration_vente.sql`, historique Supabase PROD `20261030155229 / erp_031_precontrole_exoneration_vente`. Le refus antérieur sur TEST était un état historique, **pas** l'état actuel de PRODUCTION.

Vérifications en lecture seule sur PRODUCTION :
- Fonction `public.erp_exoneration_tva_precontrole_vente(text,text[],date)` **présente**.
- `has_function_privilege` : `anon=false`, `authenticated=false`, `service_role=true` pour EXECUTE.
- Client actif `CLI-0007`, SKU actif `SKU-001` : renvoie `statut=AUCUN_DOSSIER`, `motif=AUCUNE_PREUVE_ENREGISTREE`, `autorise_facturation=false`. Les identifiants sont uniquement une lecture de référentiels existants, sans modification.
- Entrée comportant un SKU dupliqué : refus SQL attendu (`22023`), sans écriture.
- Registre : **0 attestation**, **0 validateur fiscal actif**. Migration 031 ne délivre aucune exonération, ne modifie ni `erp_sale_transaction` ni le calcul de TVA transactionnel. Elle sert seulement à la vérification préalable.
- Conseiller Supabase sécurité : uniquement avis `rls_enabled_no_policy` INFO (84 éléments préexistants/privés), aucune alerte nouvelle propre à la fonction 031 remontée. Vérifier la configuration RLS à chaque modification ultérieure.

**Statut** : code `main` et migration SQL PRODUCTION alignés. **Aucun déploiement hébergé Streamlit vérifié.** La fonction 031 n'est pas encore raccordée à la transaction fiscale réelle ni une permission d'émettre à 0 %. Règle métier inchangée : ventes à 19 % ou 0 % seulement si exonération client validée, jamais 9 % pour ce business.

---

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


## Migrations 029 et 030 — validation d'exonération renforcée et audit métier (29 octobre 2026)

- Migration `sql/029_recontrole_client_skus_validation.sql` appliquée sur **TEST et PRODUCTION** (`erp_029_recontrole_client_skus_validation`, PROD `20261029210253`). Au moment de `VALIDER`, la RPC `erp_exoneration_tva_action` refuse désormais un client devenu inactif ou une attestation dont au moins un SKU est devenu inactif. Les contrôles originels SECURITY_MANAGER, validateur fiscal distinct, impossibilité d'auto-validation et idempotence demeurent.
- Migration `sql/030_journal_acteur_metier_exoneration.sql` appliquée sur **TEST et PRODUCTION** (`erp_030_journal_acteur_metier_exoneration`, PROD `20261029210305`). Le journal privé `erp_exonerations_tva_evenements` ajoute `acteur_metier` et `operation_id` pour rattacher les actions au compte métier vérifié et à l'opération SQL, en plus de `acteur_sql`. Les contextes sont passés par paramètres locaux à la transaction. L'historique préalable, s'il existait, aurait conservé des valeurs métier nulles ; ici aucune ligne préexistante.
- Contrôles de TEST : transactions fictives `BEGIN/ROLLBACK` vérifiant le refus du client et du SKU désactivés, puis la validation, la révocation et trois événements liés au bon acteur et à la bonne opération. **0 donnée fictive conservée**.
- Contrôles de PRODUCTION par SELECT : deux colonnes d'audit présentes, journal RLS activé et inaccessible aux rôles navigateur et `service_role` en lecture directe ; exécution de l'action réservée au seul `service_role`, `anon` et `authenticated` interdits. **0 attestation, 0 portée, 0 validateur fiscal actif, 0 opération, 0 événement**.
- Code, scripts et tests : `sql/029_smoke_test_rollback.sql`, `sql/030_smoke_test_rollback.sql`, `tests/test_exoneration_sql_029.py`, `tests/test_exoneration_sql_030.py`. Les deux workflows GitHub de `d205502d85a8b4262383f0b818d6bd7d7f80c6b4`, runs `40954118969` et `40954118565`, sont **completed/success**.
- Protocole : `docs/CONTROLE_EXONERATION_VALIDATION_029_030.md`.
- **Limites maintenues** : aucun validateur fiscal réel n'a été attribué, 7 SKU actifs attendent leur classification documentée, aucun certificat d'exonération réel n'est enregistré. La RPC `erp_sale_transaction` reste historique et les contrôles de ce circuit ne l'homologuent pas. Déploiement Streamlit hébergé non confirmé.


## Précontrôle des exonérations à la vente — proposition 031 (30 octobre 2026)

- **Code publié, migration NON appliquée** : `sql/031_precontrole_exoneration_vente.sql` définit `public.erp_exoneration_tva_precontrole_vente(client_id, sku_ids, date_facture)`, exclusivement en lecture. Contrôles : client et SKU actifs, date non future, présence d'une attestation client unique et validée au plus tard à la date, attestation non révoquée, portée complète des SKU du panier. Statuts : `AUCUN_DOSSIER`, `A_BLOQUER`, `PRECONTROLE_OK`.
- **Aucun de ces statuts n'autorise une facture.** Le résultat contient toujours `autorise_facturation=false`. Une vérification atomique au sein de la future RPC transactionnelle reste obligatoire, ainsi qu'une homologation documentaire/juridique de l'exonération et de la TVA 19 % / 0 % par ligne.
- Le script prévoit une fonction `SECURITY DEFINER` avec privilège EXECUTE accordé au **seul** `service_role` (et révoqué à `PUBLIC`, `anon`, `authenticated`). Sa sécurité et son comportement doivent encore être confirmés sur TEST.
- Fichiers liés : `sql/031_smoke_test_rollback.sql` (essais fictifs uniquement sur TEST et intégralement annulés), `core/precontrole_exoneration_vente.py` (appel serveur fail-closed, non raccordé à l'UI ni à la RPC de vente), `tests/test_exoneration_sql_031.py`, `tests/test_precontrole_exoneration_vente.py`. Les tests sont ajoutés au workflow fiscal CI.
- **Blocage de déploiement** : l'appel d'application de migration 031 sur TEST a été **bloqué par les contrôles de sécurité de l'outil**. Vérification SQL en lecture seule : fonction `erp_exoneration_tva_precontrole_vente(text,text[],date)` absente de **TEST ET PRODUCTION** (`to_regprocedure(...) IS NULL`). Ne pas prétendre que la migration est appliquée, ne pas l'activer dans l'interface et ne pas entreprendre de contournement du contrôle. Les bases restent intactes.
- Prochaines actions : terminer les deux CI de `main`, faire revoir le déploiement SQL par le canal autorisé, confirmer sur TEST avec le smoke-test sous rollback, auditer les ACL, puis seulement envisager une migration en production. Préserver les dossiers vides et la facturation historique inchangée.


## Garde-fous de facturation historique avant migration 031 — 30 octobre 2026

- **Mission réalisée côté GitHub `main` uniquement** : `modules/ventes/views.py` relit les **dossiers client d'exonération** directement depuis `public.erp_exonerations_tva_clients` (table privée existante depuis migration 025). Un dossier `VALIDEE` ou `A_VALIDER` applicable aujourd'hui bloque le brouillon historique ; un dossier `REVOQUEE` ne donne aucune présomption d'exonération. Un résultat inconnu, une lecture réseau défaillante ou une liste incohérente bloque également le brouillon.
- Même vérification juste avant `valider_facture` et lors de **chaque reprise d'une validation** : le service relit le `client_id` depuis la facture réelle `public.factures`. Les anciennes factures au stade `BROUILLON` ne contournent pas le signalement d'un dossier fiscal ultérieur.
- Repère UI Ventes porté à `SOF-ERP-20261030-EXO-GARDE-01`. Cette présence **n'est pas vérifiée sur un Streamlit hébergé** : GitHub `main` + CI ne garantissent pas le déploiement.
- `core/precontrole_exoneration_vente.py` a été durci : appels RPC indisponibles/absents refusés proprement, nombres SKU booléens ou réponses non textuelles rejetés, preuves contradictoires rejetées, identifiants contrôlés. Aucune autorisation d'émettre une facture n'est renvoyée.
- Tests ajoutés dans `tests/test_precontrole_exoneration_vente.py` et `tests/test_ventes_views_security.py` : erreur réseau, dossier existant, client d'ancienne facture, reprise après apparition d'une exonération.
- **Limites importantes** : le filtrage Ventes est une prévention au niveau de l'interface uniquement, **non atomique** avec la facturation. Les appels directs à `public.erp_sale_transaction`, d'autres clients/API, ou un changement de statut concomitant doivent être sécurisés par la future RPC fiscale homologuée. Une attestation peut comporter des restrictions non encore modélisées. Ne pas prétendre que la facturation à 0 % est activée.
- **Migration 031 inchangée et toujours absente de TEST/PROD** : application SQL précédemment bloquée par contrôle de sécurité d'outil. Ce nouveau garde-fou utilise uniquement les tables 025 existantes et ne contourne pas cette interdiction. Aucune donnée fiscale ou permission BDD modifiée lors de cette livraison.


## Reprise du 30 octobre 2026 — garde fiscale sur tout historique client, y compris en reprise

- **Corrigé sur `main` :** `modules/ventes/views.py` ne limite plus le contrôle des attestations aux dossiers applicables à la date système. Toute trace de dossier d'exonération client (`A_VALIDER`, `VALIDEE` ou `REVOQUEE`) entraîne une revue fiscale avant de tenter la facturation historique à 19 %. Cette mesure volontairement conservatrice tient compte des factures d'origine/historiques et des pièces expirées ; elle peut retenir un client dont l'exonération a pris fin jusqu'à clarification documentaire.
- Le contrôle est répété dans `_execute_operation` **avant toute création de brouillon**, également lors d'une reprise après erreur réseau. La validation d'un brouillon existant est pareillement recontrôlée après lecture fraîche de `factures.client_id`. Si une exonération bloque l'opération, le statut demeure `uncertain` et l'`operation_id` d'origine est conservé : pas de nouveau brouillon ni perte d'identifiant après un éventuel COMMIT antérieur.
- Tests ajoutés : dossiers révoqués exigeant revue ; lecture sans filtre de date ; blocage avant création et lors de la reprise ; conservation d'UUID si nouveau dossier apparaît après timeout. Tests historiques de création/validation adaptés pour injecter un résultat de garde explicite.
- **Repère de l'interface Ventes : `SOF-ERP-20261030-EXO-HIST-02`**. La version hébergée de Streamlit n'a **pas** été identifiée ou vérifiée ; `main` n'est pas synonyme de déploiement effectif.
- **Aucune migration Supabase dans cette reprise.** La migration 031 est toujours absente de TEST/PRODUCTION et son application précédemment bloquée n'a pas été contournée. L'interface se base exclusivement sur la lecture de la table privée existante `erp_exonerations_tva_clients` via le serveur.
- **Limite majeure inchangée :** garde applicative non atomique ; la RPC SQL réelle `erp_sale_transaction` n'est pas raccordée aux attestations, et les appels directs ou concurrents ne sont pas couverts. La mise en production réelle d'un calcul à 0 % reste interdite sans homologation et contrôle transactionnel. Aucune attestation client ni personne habilitée ne doit être inventée.
