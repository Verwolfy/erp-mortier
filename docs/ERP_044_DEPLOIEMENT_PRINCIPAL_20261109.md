# ERP-044 — Déploiement pilote sur Supabase principal (9 novembre 2026)

## Décision du propriétaire

Le projet `erp-mortier-test` (**ffuhbmcfyexsbjwhryvj**) doit rester **INACTIVE**. Tout travail de code GitHub doit être réalisé sur la seule branche `main`, et les changements de base pour la phase essais doivent viser la base principale `erp-mortier` (**wenydirqtmkywbxbxfal**). Les données actuellement utilisées dans l'ERP sont des données d'essai non critiques. Cette autorisation n'implique pas de certifier des lois fiscales, d'inventer un régime TVA ou de compromettre l'authentification.

## Action réellement effectuée

- Migration enregistrée dans Supabase : **`20261109141222`**, nom **`erp_044_tva_sku_qualification_preview_pilote`** ; outil `apply_migration` retournant `success:true`.
- SQL exact stocké dans **`sql/044_tva_sku_qualification_preview_pilote.sql`**, branche `main`.
- Le compte des migrations natives est passé de **33 à 34**. Aucune modification du registre historique antérieur.
- Table nouvelle **`public.erp_sku_tva_qualifications`** créée, RLS activée, accès `SELECT` à `service_role` et refus à `anon` et `authenticated`.
- Fonction SQL nouvelle **`public.erp_tax_preview_classified(jsonb,date,boolean)`**, `SECURITY INVOKER`, exécutable uniquement par `service_role` parmi les rôles clients contrôlés ; calcul isolé sans écriture de facture. Fonction de protection de l'historique et son déclencheur installés.
- **`erp_sale_transaction` n'a pas été remplacée** et continue, pour l'instant, à utiliser les constantes historiques. Aucun taux fiscal ni dossier de qualification n'a été inventé ou validé par cet assistant.

## Tests et contrôles

1. Tests GitHub sur le SHA `3134b0e2fd0bafd030bce097901bf73a8c83f8a7` :
   - [PostgreSQL 17 éphémère](https://github.com/Verwolfy/erp-mortier/actions/runs/42632053570) : **success**. Le workflow exécute précisément le fichier SQL ERP-044 puis les tests SQL fictifs.
   - [Tests ERP](https://github.com/Verwolfy/erp-mortier/actions/runs/42632053592) : **success**.
   - [Audit de réconciliation](https://github.com/Verwolfy/erp-mortier/actions/runs/42632053565) : **success**.
2. Contrôle direct sur Supabase principal après migration : objets SQL présents, RLS vrai, aucune autorisation `SELECT` de la nouvelle table à `anon` ou `authenticated`, pas d'`EXECUTE` sur la RPC pour ces deux rôles, `service_role` autorisé ; déclencheur de protection présent.
3. **Test réel et temporaire sur la base principale**, dans une transaction explicite `BEGIN` / `ROLLBACK` : qualification *fictive* temporaire d'un SKU DEMO ; appel de la RPC avec rôle `service_role`, comparaison du calcul au taux réellement stocké dans `parametres_reglementaires` ; succès sans erreur. Vérification après `ROLLBACK` : **0 qualification conservée**, aucune trace de donnée fictive enregistrée.
4. Projet Supabase TEST relu ensuite : toujours **INACTIVE**.

## Divergence détectée et à résoudre avant intégration

Le schéma principal possédait déjà `public.erp_sku_fiscalite` : **2 lignes `A_VALIDER`**, **0 ligne `VALIDEE`**, catégories `NORMAL`/`REDUIT`/`EXONERE`/`HORS_CHAMP`, justificatif juridique, validation datée, RLS actif. Cette table est **distincte** de la nouvelle `erp_sku_tva_qualifications` créée par ERP-044, elle-même vide.

**Ne pas maintenir deux sources d'autorité TVA par SKU.** Avant d'activer un écran de qualification ou une facture datée, décider par comparaison des contrats de données et des usages existants si la RPC pilote doit lire la table préexistante `erp_sku_fiscalite` (option privilégiée, sans recopier des données `A_VALIDER` comme confirmées) ; conserver l'historique et la trace des décisions. Les deux lignes existantes restent non validées. Aucune classification n'est inventée. Le nouveau pilote n'est pas encore activé dans la facturation ni connecté à l'interface.

## Prochaine séquence sans approbation non nécessaire

1. Réconcilier les modèles de qualification TVA existant et pilote, tests SQL et Python d'abord ; appliquer sur **Supabase principal**, sans utiliser TEST.
2. Ajouter la preuve du taux et du régime de chaque ligne facture et la règle de répartition de remise globale, en préservant les factures historiques.
3. Préparer la mise à jour atomique de `erp_sale_transaction`, avec contrôle du scénario espèces/timbre et des avoirs ; aucune homologation fictive.
4. Vérifier par les tests E2E et les privilèges avant de retirer les anciennes constantes de production.

**Statut** : déploiement **technique pilote** réussi sur la base principale ; facturation fiscale active et homologation non terminées.
