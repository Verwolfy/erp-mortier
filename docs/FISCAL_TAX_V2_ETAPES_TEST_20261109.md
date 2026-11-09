# TAX-V2 — Passage de la simulation à la facturation réglementaire (9 novembre 2026)

## Résultat de ce lot

Le dépôt `Verwolfy/erp-mortier` conserve une seule branche `main`. Une **migration candidate non exécutée** a été ajoutée :
`sql/supabase_pending/erp_tax_classification_preview_CANDIDAT_NON_EXECUTE.sql`.

Elle prépare :
1. `public.erp_sku_tva_qualifications` : codes TVA `TVA_TAUX_NORMAL` ou `TVA_TAUX_REDUIT`, SKU lié à `sku_conditionnement`, dates d'effet/de fin, statut (`a_confirmer`/`confirmee`/`rejetee`), source, dates et identifiant du validateur ;
2. une barrière anti-rétroactivité : aucune suppression de ligne de qualification, aucune modification d'une qualification déjà confirmée ou rejetée ; changement de règle par **nouvelle version datée** ;
3. `public.erp_tax_preview_classified(jsonb,date,boolean)`, fonction `STABLE SECURITY INVOKER` limitée à `service_role` : calcul *sans écriture* de TVA par SKU, lecture de la **classification stockée en serveur**, contrôle du référentiel `parametres_reglementaires`, de la date et de l'unicité des versions ; refus des espèces, des SKU inactifs, des incohérences, exemptions et classes non prises en charge.

Aucune valeur juridique, aucun taux fiscal, aucune classification SKU fictive n'a été ajoutée à la production.

## Preuve technique

- `tests/test_tax_preview_sql_candidate.py` : contrat statique SQL, parseur PostgreSQL via `pglast`, analyse des deux fonctions PL/pgSQL et invariants d'accès.
- `tests/sql/tax_preview_fixture_pg17.sql` : uniquement des rôles, SKU et taux **fictifs** sur une base jetable.
- `tests/sql/tax_preview_integration_pg17.sql` : calculs, parité de deux taux fictifs, droit de `service_role`, absence de droits clients directs, refus des taux fournis par un client, classifications incomplètes, espèces, mauvais montants, doublons, et historique immuable.
- `.github/workflows/tax-preview-pg17.yml` : le service Docker `postgres:17` fonctionne sur le runner GitHub ; aucune clé de production ni projet Supabase TEST n'est configuré. Le mot de passe est local et éphémère au runner.

L'existence de cette CI constitue une preuve *technique SQL isolée*, mais **pas une recette complète** de `erp_sale_transaction` sur le vrai schéma ERP.

## Intégration applicative non activée

`modules/ventes/fiscal_preview.py` fournit `simuler_tva_sql` : un adaptateur **lecture seule** exigeant un client interne explicitement injecté, une date fiscale ISO, des montants monétaires sous forme de chaînes et un panier de SKU. Il n'accepte **aucun `code_tva` ni attestation envoyés par le navigateur** : la qualification provient de `erp_sku_tva_qualifications` consultée par la fonction PostgreSQL. Il contrôle à la réception chaque code et taux, les sources, les dates, les arrondis TVA, le détail des lignes et les sommes globales. Toute réponse absente, float, incohérente ou erreur RPC bloque l'aperçu ; aucun appel à la transaction `erp_sale_transaction`.

`tests/test_fiscal_preview_rpc.py` teste ce pont avec des fausses réponses : deux taux fictifs, refus de données forgées, des erreurs réseau, dates invalides, taux ou totaux incohérents et absence d'écriture. **Ce module n'est pas branché à l'écran de création des factures**. Sans déploiement préalable de la candidate en TEST, l'appel RPC est normalement indisponible, ce qui n'affecte pas le circuit existant.

## Contrôles exécutés

- [GitHub Actions PostgreSQL 17 isolé #42623241192](https://github.com/Verwolfy/erp-mortier/actions/runs/42623241192) : **success**, exécution réelle de la candidate sur une base jetable, tous contrôles SQL réussis.
- [GitHub Actions tests ERP #42624303327](https://github.com/Verwolfy/erp-mortier/actions/runs/42624303327) et [audit #42624303505](https://github.com/Verwolfy/erp-mortier/actions/runs/42624303505) : **success**, **3 233 tests réussis**, zéro échec, un avertissement de dépendance, sur le SHA `8b639693` incluant l'adaptateur Python et ses tests. Les commits purement documentaires ultérieurs restent soumis à la CI.

## Blocages métier et techniques vérifiés dans Supabase

- Production `wenydirqtmkywbxbxfal` : actif.
- TEST `ffuhbmcfyexsbjwhryvj` : `INACTIVE`. Ne pas déclencher une éventuelle facturation liée au rétablissement du service sans vérifier les coûts.
- `public.parametres_reglementaires` contient les codes de référence `TVA_TAUX_NORMAL` et `TVA_TAUX_REDUIT`, avec dates et sources. **Aucune décision de TVA par SKU ne peut être déduite de ces références générales**.
- `public.sku_conditionnement` ne possède actuellement aucune colonne de code TVA juridique qualifié. Le schéma existant `factures` stocke `taux_tva` global et `lignes_facture` ne dispose pas de colonnes de TVA par ligne. Il ne faut pas enregistrer une facture mixte sous un taux global.
- La RPC **production** `erp_sale_transaction` conserve `0.19`, `0.01` et `2500` en dur ; elle ne lit toujours pas `parametres_reglementaires`. Le code Python `modules/ventes/service.py` contient les mêmes constantes. Les simulations TAX-V2 **ne remplacent pas ces chemins actifs**.
- La procédure existante `sql/013_facturation_parametree.sql` est un autre **brouillon non déployable** : elle utilise un code fictif `TVA_VENTE_TAUX`, n'a pas de qualification produit par ligne et ne convient pas comme remplacement de la RPC de production.

## Suite à exécuter après ce lot

1. **Valider la CI PostgreSQL jetable** et les tests Python sans erreur ; corriger les défauts, consigner le SHA `main`.
2. **Faire homologuer** la qualification TVA par SKU et le régime fiscal applicable à l'entreprise avec une source juridique auditable. Les taux généraux ne suffisent pas à déduire l'application produit. Ne pas mélanger les codes d'une ancienne maquette (`TVA_VENTE_TAUX`) avec les codes confirmés `TVA_TAUX_NORMAL/REDUIT` sans contrat de correspondance.
3. **Rétablir un environnement TEST isolé** après vérification de l'impact financier et du contrôle d'accès ; appliquer la candidate puis exécuter les tests d'intégration sous les rôles réels.
4. **Adapter le modèle facture** : inclure `code_tva`, `taux_tva`, `montant_tva` et la preuve de classification de chaque ligne, établir une règle de répartition de toute remise globale, traiter les avoirs et les exemptions. Interdire l'enregistrement d'une facture mixte dans le seul champ global actuel.
5. **Modifier simultanément la RPC et le service Python** : même calcul daté par ligne, validation SQL atomique en production, traçabilité de l'opération, protection contre les retries, conservation des ID légaux et des mouvements de stock existants. Retirer alors, et seulement alors, les six constantes legacy. Ne pas modifier les données historiques sans procédure d'audit.
6. **Recette E2E** : brouillon/validation/avoir/livraison, privilèges, reprise après timeout, écarts TVA, clôture SCF, Streamlit authentifié et preuve SHA déployé. Homologation comptable et juridique avant activation.

## Invariants de sécurité

**Cette candidate n'est pas à exécuter sur la production.** Elle crée des objets, même si son calcul n'écrit rien : il s'agit bien d'une migration DDL non appliquée. Les données DEMO/SIM, le registre fiscal réel, les dossiers d'exonération, les règles CNAS `a_confirmer` et les contrôles RLS/GRANT existants restent intacts. Toute mise en service fiscale requiert une vérification externe des textes et du traitement des SKU.

**État global** : préparation et tests techniques uniquement ; migration active et conformité non terminées.
