# Rapprochement quantitatif SCF / coûts industriels — campagne du 6 novembre 2026

## Résultat : VALIDÉ sur Supabase TEST, puis déployé en PRODUCTION

### Environnements
- GitHub : `Verwolfy/erp-mortier`, branche `main`.
- TEST : Supabase `ffuhbmcfyexsbjwhryvj`.
- PRODUCTION : Supabase `wenydirqtmkywbxbxfal`.
- Migration : `sql/040_couts_industriels_plafond_ligne_scf.sql`.

### Fonction ajoutée
1. Champ `erp_cost_pool_scf_evidence.scf_ligne_id` obligatoire, référencé à `scf_lignes(ligne_id)` avec unicité globale.
2. Preuve rapprochée à une **ligne précise au débit** de la même pièce SCF `VALIDEE`. Refus de lien sans débit positif ou sans correspondance pièce / ligne.
3. Montant analytique `erp_cost_pools.montant_dzd` plafonné à `scf_lignes.debit`, aussi bien au lien initial qu'au changement de statut `DOCUMENTE` et à la validation de période.
4. Toute utilisation de la même ligne pour deux pools est refusée par la contrainte `UNIQUE(scf_ligne_id)`.
5. Vue `erp_cost_scf_reconciliation` en `security_invoker=true` pour afficher référence de pièce, ligne, compte, débit, montant imputé, solde et `rapprochement_ok`. SELECT autorisé uniquement au rôle serveur.
6. Service Python `modules/production/cost_service.py` : vérification UUID pièce, ID ligne SCF, lien et plafond. Formulaire Streamlit `modules/production/cost_views.py` mis à jour pour saisir une ligne SCF et afficher le rapprochement.
7. Aucun changement du CUMP, des stocks ou des écritures comptables.

### Preuves des tests réels sur TEST
- Migration 040 : `success=true`.
- `sql/test_isole/20261105_couts_industriels_referentiel_ROLLBACK.sql` : verdict `COST_REFERENCE_OK`. Allocations OF1 = 70 DZD, OF2 = 140 DZD, total 210 DZD.
- Cas négatifs intégrés dans le scénario : imputation 201 DZD face à une ligne au débit de 200 DZD **refusée** ; deuxième pool sur la même ligne SCF **refusé** par `unique_violation`. Refus du statut `DOCUMENTE` sans pièce; validation de période sans toutes les preuves; suppression de preuve après validation.
- Vue de rapprochement : deux lignes à `rapprochement_ok=true`, chacune débit 200 DZD, solde non imputé positif ou nul.
- `sql/test_isole/20261105_couts_industriels_acl_ROLLBACK.sql` : verdict `COST_ACL_OK`.
- Après `ROLLBACK`, contrôle séparé : 0 preuve, 0 pool, 0 période, 0 pièce SCF fictive et 0 compte SCF fictif.
- TEST : vue `erp_cost_scf_reconciliation` présente, `authenticated` sans SELECT, `service_role` avec SELECT.

### CI GitHub (commit 22eba920b59ccc93709d9c4a19860092d7943a4c)
- Tests ERP complets : **success** — https://github.com/Verwolfy/erp-mortier/actions/runs/42198542726
- Audit de réconciliation : **success** — https://github.com/Verwolfy/erp-mortier/actions/runs/42198542581

### Preuve de déploiement en production
Migration `erp_industrial_cost_scf_debit_ceiling_20261106` : `success=true`.

Contrôle SQL de production après déploiement :
- `preuves=0`, `charges=0`, `periodes=0`. Aucun montant ni pièce fictive ajouté.
- Vue `erp_cost_scf_reconciliation` présente.
- Colonne `scf_ligne_id` : `NOT NULL` confirmée.
- `authenticated` : SELECT=false sur la vue ; `service_role` : SELECT=true.

### Limites et prochaines étapes
- Une ligne débitée au SCF ne prouve **pas**, à elle seule, l'éligibilité industrielle de la dépense : validation métier par Finance indispensable.
- L'unicité interdit de répartir une ligne SCF sur plusieurs pools, choix conservateur contre le double comptage.
- Les coûts analytiques restent **séparés** de la valorisation officielle CUMP et des écritures SCF.
- Il faut encore réaliser un test navigateur authentifié réel avec profil Production+Finance, puis profil limité; les tests SQL et tests Python mockés ne suffisent pas à qualifier ce parcours.
- Préparer et valider une règle métier pour le contrôle de concordance de nature comptable, période, assiette et origine de la dépense avant toute automatisation supplémentaire.
