# Audit de réconciliation ERP — 2026-11-05

## Portée et preuves
- Dépôt : `Verwolfy/erp-mortier`, branche `main`, commit contrôlé `638e259539b5fa9f2d127b6625913d3994c5f137`.
- CI de réconciliation, run [42064409724](https://github.com/Verwolfy/erp-mortier/actions/runs/42064409724) : `controler` conclu `success`, dont « Suite complète ERP », compilation, tests scanner et analyse PowerShell. Le scanner des taux est **non bloquant** dans le workflow ; un succès CI ne prouve pas l'absence totale de constantes fiscales.
- Supabase principale `wenydirqtmkywbxbxfal` : vérifications en **lecture seule**. Au contrôle, 90 tables `public`, aucune sans RLS ; `supabase_migrations.schema_migrations` possède 23 lignes, de `20261027200803` à `20261031220121` ; `public.schema_migrations` existe mais contient 0 ligne.
- `docs/migration_evidence_20261101.json` référence les 23 versions et leurs candidats documentaires. **Ce manifeste n'atteste pas l'identité du SQL exécuté**. Les versions 20261031204336 et 20261031220121 renvoient à des fichiers du **dépôt site**, non au dépôt ERP. Ne pas les rejouer depuis l'ERP.

## Branches distantes vérifiées (comparaison avec main)
| Branche | En avance | En retard | Conclusion |
|---|---:|---:|---|
| feat/lot11-nextgen-export-readonly-20261101 | 0 | 239 | Ancêtre de main |
| feat/lot12-nextgen-complete-reads-20261101 | 0 | 232 | Ancêtre de main |
| feat/lot13-migration-evidence-readonly-20261101 | 0 | 223 | Ancêtre de main |
| feat/nextgen-crm-inbox-readonly-20261101 | 2 | 254 | main a des garde-fous CRM plus récents |
| feat/nextgen-crm-ui-fingerprint-20261101 | 1 | 249 | test fingerprint identique sur main ; vues plus récentes |
| feat/nextgen-privacy-dual-gate-20261101 | 1 | 252 | module de confidentialité identique sur main |
| feat/nextgen-sku-qualification-readonly-20261101 | 5 | 247 | main a pagination, export et tests enrichis |

Ces branches divergentes ne doivent **pas** être fusionnées aveuglément : une intégration de code ancien risque de retirer des contrôles nouveaux. Aucun merge ni suppression de branche attesté à ce stade.

## Décisions techniques / prochaines vérifications
1. Obtenir la preuve du SQL exact des 23 migrations ; comparer le schéma réel avec les migrations candidates avant d'écrire dans `public.schema_migrations`. Ne jamais remplir ce registre à partir des noms seuls.
2. Comparer sur l'état réel toutes les fonctions, contraintes, triggers, vues, indexes, politiques RLS et GRANT concernés. Le seul comptage RLS n'est pas un audit de permissions.
3. Conserver les protections récentes de `main` ; ne fusionner que les modifications absentes et testées. Après fusion réussie, supprimer la branche correspondante selon la consigne utilisateur. L'outil GitHub disponible pendant cet audit **ne propose pas de suppression de branche**, donc aucune suppression n'a été effectuée.
4. Ne pas inventer de taux ni activer de paramètres réglementaires incertains. Toute modification à fort impact fiscal ou aux RLS/GRANT reste soumise aux points d'arrêt convenus.

**État** : audit documentaire, sans SQL d'écriture, sans fusion, sans suppression, sans modification des références fiscales.
