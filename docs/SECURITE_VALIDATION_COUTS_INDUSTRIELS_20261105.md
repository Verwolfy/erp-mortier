# Durcissement des coûts industriels — clôture 05/11/2026

## Action réalisée
Continuité du référentiel `erp_cost_*` déjà publié et déployé sur TEST + production (migrations 034 et 035).

### Risque découvert
Le rôle serveur `service_role` pouvait encore effectuer `UPDATE public.erp_cost_periods SET statut='VALIDE'` sans l'audit imposé par `erp_cost_validate_period`. Le simple trigger 034 ne protégeait pas la transition directe depuis BROUILLON.

### Correction SQL versionnée et déployée
- **036** `sql/036_couts_industriels_validation_privileges.sql` :
  - Refuse `INSERT` avec statut autre que `BROUILLON`.
  - Révoque `UPDATE,DELETE` du rôle `service_role` sur `erp_cost_periods` (garde SELECT/INSERT).
  - Remplace `erp_cost_validate_period(text)` par une fonction `SECURITY DEFINER` avec `search_path` explicite et EXECUTE limité à `service_role`; elle vérifie pièces DOCUMENTE, présence des assiettes et audit avant de valider.
  - Ne change pas les fonctions métiers CUMP / clôture OF ni les écritures SCF.
- **037** `sql/037_cost_guard_security_definer.sql` :
  - Le test du 036 seul a trouvé qu'un trigger sur pools/drivers exécutait `SELECT ... FOR UPDATE` sur la période, ce qui requérait un droit UPDATE refusé.
  - Le trigger `erp_cost_check_editable()` fonctionne désormais comme `SECURITY DEFINER`, propriétaire `postgres`, sans EXECUTE accordé au rôle serveur ou aux clients.
  - Les écritures dans les pools/drivers restent autorisées sur BROUILLON mais refusées après VALIDE.

Les migrations **036 et 037** ont été appliquées avec succès sur **TEST** `ffuhbmcfyexsbjwhryvj` puis sur **production** `wenydirqtmkywbxbxfal`.

### Preuves SQL réelles de TEST
- `sql/test_isole/20261105_couts_industriels_acl_ROLLBACK.sql` → **`COST_ACL_OK`**. Scénarios : refus d'INSERT direct VALIDE, refus d'UPDATE direct service_role, refus de validation de pool SIMULATION, validation autorisée et contrôlée via la RPC avec DOCUMENTE, modification après validation refusée.
- `sql/test_isole/20261105_couts_industriels_referentiel_ROLLBACK.sql` → **`COST_REFERENCE_OK`**. Allocations OF1=70 DZD et OF2=140 DZD; total 210 DZD, cout analytique 370/340 DZD.
- `sql/test_isole/20261105_couts_industriels_authentifie_refus_ROLLBACK.sql` : contrôle équivalent exécuté via `SET LOCAL ROLE authenticated`, verdict **`AUTHENTICATED_DENIED_OK`**. Accès direct SELECT et RPC de validation tous deux refusés.
- Audit indépendant après ROLLBACK : **0 période, 0 pool, 0 driver et 0 OF de test**, droits `service_role` UPDATE=false, EXECUTE RPC=true; `authenticated` EXECUTE=false.
- Prouvé sur TEST que `erp_cost_validate_period` et `erp_cost_check_editable` ont SECURITY DEFINER et propriétaire postgres.

### Contrôle production réel
- Après 036+037 : `periods=0`, `pools=0`, `drivers=0`. Aucune donnée fictive persistée.
- `server_can_update_directly=false`, `server_can_create_brouillon=true`, `server_can_validate_rpc=true`, `auth_can_validate_rpc=false`, les deux fonctions SQL sont SECURITY DEFINER.
- Aucune fonction de fabrication / stock / CUMP modifiée.

### Tests Python et CI
- `tests/test_industrial_cost_service_access.py` publié. Couvre refus sans droits Production+Finance en lecture/écriture, validation des montants et création d'une période BROUILLON sous droits serveur mockés.
- Le commit `78086274dcb62a379b9256de0a941e2528f6482b` a **deux workflow CI réussis** :
  - tests ERP `https://github.com/Verwolfy/erp-mortier/actions/runs/42121756553`.
  - audit lecture seule `https://github.com/Verwolfy/erp-mortier/actions/runs/42121756486`.
- Commit 037 `71fe262ce75e638904b806f337f329052ebce1d6`, CI **deux workflows réussis** :
  - tests ERP `https://github.com/Verwolfy/erp-mortier/actions/runs/42122309186`.
  - audit `https://github.com/Verwolfy/erp-mortier/actions/runs/42122309249`.

### Limites restantes
- Aucun test **navigateur avec authentification de compte réel** : l'interface Streamlit a été couverte par tests CI mockés, pas une session utilisateur; ne pas prétendre autrement.
- Le statut DOCUMENTE repose sur une référence documentaire manuelle. Le système ne vérifie pas encore l'existence de la pièce dans le registre documentaire; attention aux coûts fictifs camouflés par une référence saisie.
- La clé serveur reste uniquement côté serveur; les droits métiers Production et Finance sont revérifiés depuis Supabase par le service Python.
- Les fonctions SQL SECURITY DEFINER ne doivent jamais être accordées au public; les comptes SQL propriétaires disposent naturellement de droits de maintenance exceptionnels.
- Confirmer l'état TEST `INACTIVE` après demande de pause.

## Prochaine étape recommandée
Vérifier une vraie session navigateur Streamlit avec un compte habilité et un compte limité, puis intégrer une vérification d'existence/référence documentaire avant DOCUMENTE. Exiger qu'aucune validation simulée ne devienne une valeur stock/comptable sans approbation.

## Vérification terminale
- Supabase TEST : état **INACTIVE** confirmé après suspension.
- Workflows associés au commit du rapport `8c9e0e7500abc14bbbf422a3cca5740316e6fe00` : tous deux **success** :
  - [Tests ERP complets](https://github.com/Verwolfy/erp-mortier/actions/runs/42122645172)
  - [Audit de réconciliation](https://github.com/Verwolfy/erp-mortier/actions/runs/42122644991)
- Une vraie connexion utilisateur à l'interface Streamlit n'a pas été testée : seulement les tests applicatifs simulés et les tests SQL des rôles.
