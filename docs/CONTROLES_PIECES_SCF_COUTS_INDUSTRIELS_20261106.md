# Preuve SCF obligatoire pour les coûts industriels — 06/11/2026

## Résultat
**Migration 038 déployée sur Supabase TEST et production.** La mention `DOCUMENTE` ne peut plus résulter d'un simple texte de référence : un lien structuré vers une pièce comptable `public.scf_pieces` réellement `VALIDEE` avec `date_validation` non nulle est obligatoire.

## Fichiers de code GitHub main
- `sql/038_couts_industriels_pieces_scf_validees.sql` : nouvelle table `erp_cost_pool_scf_evidence` (FK pool et pièce SCF, unicité de pièce), RLS et permissions, vérification par triggers et par RPC de validation de période.
- `modules/production/cost_service.py` : contrôle serveur des droits Production+Finance existants, référence UUID de pièce SCF, refus des pièces absentes ou non validées, upsert reprenable en cas d'incertitude réseau puis passage DOCUMENTE.
- `modules/production/cost_views.py` : formulaire UUID SCF et motif du rattachement.
- `tests/test_industrial_cost_scf_evidence_contract.py` : assertions statiques de garde-fous.
- `sql/test_isole/20261105_couts_industriels_referentiel_ROLLBACK.sql` et `..._acl_ROLLBACK.sql` : scénarios compatibles SCF, avec comptes mouvementables fictifs, deux pièces équilibrées, validées par la vraie logique SCF, le tout sous ROLLBACK.

## Tests SQL réellement exécutés sur TEST
- `COST_REFERENCE_OK` : répartition 70 DZD et 140 DZD sur deux OF, conservation 210 DZD.
- `COST_ACL_OK` : droits du rôle serveur et validation via RPC.
- Refus d'une charge DOCUMENTE sans lien SCF validé testé directement en SQL.
- Suite SQL exécutée en `BEGIN ... ROLLBACK`, sans persistance des données fictives.
- Vérification indépendante après ROLLBACK : 0 pièce fictive, 0 compte fictif, 0 OF fictif, 0 pool et 0 période de test, 0 lien de preuve.
- Accès direct `authenticated` à la table des preuves : refusé ; le rôle serveur possède le droit d'insertion.

## CI confirmée
Commit `9fc89c229cd8ee50104d4733253d135caf0f05a2` :
- [Suite ERP complète : succès](https://github.com/Verwolfy/erp-mortier/actions/runs/42195599915)
- [Audit de réconciliation : succès](https://github.com/Verwolfy/erp-mortier/actions/runs/42195599943)

## Production — vérification après migration
- `erp_cost_pool_scf_evidence` présente.
- 0 preuve, 0 charge, 0 période; aucune donnée de démonstration importée.
- `authenticated` n'a pas SELECT sur cette table ; `service_role` peut ajouter un lien.
- **0 pièce SCF validée en production au moment du contrôle.** Les charges restent SIMULATION tant qu'une vraie pièce SCF n'est pas validée.
- Aucun changement dans le calcul CUMP, la clôture OF, les stocks, la fiscalité ou les écritures comptables.
- L'existence d'une pièce SCF validée **ne prouve pas à elle seule** que sa totalité ou une fraction de son montant est imputable à une charge industrielle. Le motif d'affectation et la revue documentaire restent nécessaires.

## Pistes de contrôle restant à mener
1. Test interactif Streamlit avec un compte authentifié en Production+Finance et un compte limité. Non testé en vrai navigateur.
2. Contrôler formellement une piste d'approbation de l'imputation et vérifier l'absence de double imputation d'une pièce dans plusieurs charges (l'unicité actuelle impose déjà une seule charge par pièce).
3. Mettre en place si nécessaire la réconciliation quantitative pièce SCF ↔ coût imputé avec règles comptables approuvées, sans inventer de données officielles.
4. Supabase TEST doit être à nouveau suspendu `INACTIVE`.
