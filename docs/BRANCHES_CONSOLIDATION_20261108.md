# Consolidation des branches de Sofiane ERP — 8 novembre 2026

## Autorisation et objectif
Le propriétaire demande explicitement de supprimer toutes les branches secondaires, après vérification et fusion des éléments utiles. **Une seule branche à conserver : `main`.** Ne supprimer aucun tag, fichier métier, migration ou donnée.

## État avant nettoyage
- Dépôt : `Verwolfy/erp-mortier`.
- `main` initial : `f7efb4eff4c48fb4d4ede1e83ea97d747cfee037`.
- 45 branches distantes, soit 44 branches secondaires, aucune protégée.
- 40 branches secondaires sans commit en avance sur `main` (dont la PR #75 fusionnée).
- Quatre branches historiques divergentes, mais chacune possède une PR fusionnée et un `head_sha` correspondant au SHA réel de sa branche : PR #31, #32, #33 et #34. Leur arbre de fonctionnalité a déjà été repris sur `main` ; **ne pas fusionner à nouveau ces anciens commits**.
- Aucune PR ouverte au moment du contrôle.
- Test et audit de `main` initial réussis : [tests](https://github.com/Verwolfy/erp-mortier/actions/runs/42517636281) et [audit](https://github.com/Verwolfy/erp-mortier/actions/runs/42517636453).

## Photographie des branches avant suppression
| Branche | SHA constaté | Qualification |
|---|---|---|
| `design/sec-crm03-idempotent-rpc-test-only-20261108` | `17775a278fa2` | 0 commit en avance de main |
| `feat/aide-contextuelle-erp-20261107` | `a85e16ba9233` | 0 commit en avance de main |
| `feat/couts-prevalidation-fiabilisation-20261106` | `44b485a27f3c` | 0 commit en avance de main |
| `feat/dashboard-demo-isole-20261107` | `680c3a72f89c` | 0 commit en avance de main |
| `feat/dashboard-kpi-pilotage-20261107` | `b712bc6bde22` | 0 commit en avance de main |
| `feat/lot11-nextgen-export-readonly-20261101` | `6e31ac2f8337` | 0 commit en avance de main |
| `feat/lot12-nextgen-complete-reads-20261101` | `0486d4cdf45b` | 0 commit en avance de main |
| `feat/lot13-migration-evidence-readonly-20261101` | `54fcefd5cce5` | 0 commit en avance de main |
| `feat/nextgen-crm-inbox-readonly-20261101` | `1165a6c7ae04` | PR #31 fusionnée (historique divergent) |
| `feat/nextgen-crm-ui-fingerprint-20261101` | `975b6e9feb1e` | PR #33 fusionnée (historique divergent) |
| `feat/nextgen-privacy-dual-gate-20261101` | `adc2d4a5d96b` | PR #32 fusionnée (historique divergent) |
| `feat/nextgen-sku-qualification-readonly-20261101` | `c1818da93af1` | PR #34 fusionnée (historique divergent) |
| `feat/p0-integration-environment-preflight-20261108` | `734039c3df66` | 0 commit en avance de main |
| `feat/p0-workflow-contracts-release-provenance-20261108` | `786ff71d86c9` | 0 commit en avance de main |
| `fix/anti-doublons-tier-edition-20261107` | `ebe7a7e852a8` | 0 commit en avance de main |
| `fix/anti-doublons-tiers-20261107` | `79ccdf555dbb` | 0 commit en avance de main |
| `fix/couts-audit-zero-20261106` | `b6a2f4ef564f` | 0 commit en avance de main |
| `fix/couts-preflight-nonzero-20261107` | `e4e148276fb9` | 0 commit en avance de main |
| `fix/dashboard-demo-ux-visual-20261107` | `9e6721104df2` | 0 commit en avance de main |
| `fix/documents-fpdf2-warnings-20261107` | `6a205d08d697` | 0 commit en avance de main |
| `fix/incident-dashboard-provenance-typeerror-20261108` | `35c6972068d8` | 0 commit en avance de main |
| `fix/p0-secret-input-gate-20261108` | `116a4c6b8478` | 0 commit en avance de main |
| `fix/streamlit-couts-deploiement-20261107` | `0110ec76fd06` | 0 commit en avance de main |
| `ops/streamlit-observation-20261107` | `24632d1f9fed` | 0 commit en avance de main |
| `perf/dashboard-lazy-panels-20261108` | `4a89f7e6aa96` | 0 commit en avance de main |
| `perf/dashboard-period-read-cache-20261108` | `9a641ca4ce79` | 0 commit en avance de main |
| `perf/dashboard-provenance-projection-20261108` | `54b14a599bc7` | 0 commit en avance de main |
| `perf/erp-034-fk-index-gap-20261108` | `6633affdbfb9` | 0 commit en avance de main |
| `perf/lot06-stocks-lazy-20261108` | `c0bacea3be10` | 0 commit en avance de main |
| `perf/lot06b-stocks-category-lazy-20261108` | `471e5307b2fa` | 0 commit en avance de main |
| `perf/lot07-achats-lazy-20261108` | `30b65a11c2dd` | 0 commit en avance de main |
| `perf/lot08-production-lazy-20261108` | `8037ff4989c0` | 0 commit en avance de main |
| `perf/lot09-crm-lazy-20261108` | `71eafda3207f` | 0 commit en avance de main |
| `perf/lot10-ventes-lazy-20261108` | `21b2130e991f` | 0 commit en avance de main |
| `perf/lot11-finance-lazy-20261108` | `4eb6226bddac` | 0 commit en avance de main |
| `perf/lot12-rh-lazy-20261108` | `b90538525eea` | 0 commit en avance de main |
| `perf/lot13-security-users-lazy-20261108` | `35580e7d047b` | 0 commit en avance de main |
| `perf/lot14-admin-referentials-lazy-20261108` | `ad69f6fd1724` | 0 commit en avance de main |
| `perf/opt04-render-query-metrics-20261108` | `352fd58e22f3` | 0 commit en avance de main |
| `perf/opt05-page-client-reuse-20261108` | `fb284ccbb0e9` | 0 commit en avance de main |
| `security/sec-admin-fresh-rbac-20261108` | `45b309fcffab` | 0 commit en avance de main |
| `security/sec-crm-fresh-rbac-20261108` | `d53a3347ae23` | 0 commit en avance de main |
| `security/sec-crm-uncertain-insert-20261108` | `2bfa02c698bf` | 0 commit en avance de main |
| `test/dashboard-demo-streamlit-smoke-20261107` | `739ebfabc052` | 0 commit en avance de main |

## Procédure de suppression contrôlée
Le workflow temporaire `.github/workflows/cleanup-only-main-20261108.yml` est limité à un commit de lancement spécifique sur `main`, avec droit `contents:write` pour supprimer les références distantes. Avant toute suppression, il doit :
1. Valider que le `main` actuel descend du SHA initial cité plus haut.
2. Refuser toute branche supplémentaire non inventoriée, tout changement de SHA ou toute branche protégée.
3. Refuser de supprimer une branche portant une PR encore ouverte.
4. Pour chaque branche, vérifier qu'elle est un ancêtre de `main`, ou, pour les quatre historiques divergentes, que la PR dédiée est fusionnée avec un `head_sha` identique et un commit de fusion inclus dans `main`.
5. Ne supprimer **que** les références `refs/heads/<branche>` vérifiées. Reprise idempotente si une exécution partielle a déjà supprimé une partie des références.
6. Confirmer ensuite, via l'API GitHub, qu'il reste **uniquement `main`** ; consigner la sortie des Actions. En cas d'échec de droits, ne pas prétendre que les branches sont effacées.

**Périmètre :** uniquement les branches GitHub distantes. Les branches locales d'un ordinateur externe ne sont pas accessibles au connecteur ; elles doivent être nettoyées séparément si nécessaire.

## Résultat exécuté et vérifié — 8 novembre 2026 à 20:09 UTC

**Nettoyage distant terminé.** Workflow [GitHub Actions #42518493728](https://github.com/Verwolfy/erp-mortier/actions/runs/42518493728) : état `completed`, conclusion `success`. Les journaux horodatés contiennent **44** mentions `SUPPRIMÉE :`, soit 44 références distantes effectivement supprimées.

**Contrôle final API GitHub** : `GET /repos/Verwolfy/erp-mortier/branches?per_page=100` retourne un tableau d'une seule entrée : `main`, SHA `ef08d88c811b80cf14a16901c4400f15ecf50b91` juste après nettoyage.

Aucune migration Supabase, aucune mutation de données ni aucun changement des droits SQL. Le script de nettoyage est **à usage unique** : son déclenchement exige la modification de son propre workflow sur `main` ET le message de commit exact `chore: consolidation finale des branches (run-once)`.

**Limite de portée** : nettoyage des branches *distantes GitHub* seulement ; les branches locales éventuelles sur un poste utilisateur ne sont pas détectables ici.

**Prochaines optimisations ERP indépendantes** : refonte de la fiscalité historique codée en dur (`modules/ventes/service.py`, `sql/005_atomic_sales.sql`, RPC production `erp_sale_transaction`) ; contrôle de la comptabilité SCF/paie ; validation en environnement Supabase TEST ; preuve du SHA réellement déployé dans Streamlit ; homologation réglementaire par un expert-comptable algérien. Les 18 index FK de `sql/supabase_pending/erp_034_fk_indexes_CANDIDAT_NON_EXECUTE.sql` restent **non exécutés** en production.
