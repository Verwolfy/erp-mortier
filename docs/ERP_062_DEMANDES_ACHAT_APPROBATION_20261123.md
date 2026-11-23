# ERP-062 — Demandes d'achat, approbation et conversion BC (préparation validée)
**Date : 23 novembre 2026** · Dépôt `Verwolfy/erp-mortier` · Supabase principal `wenydirqtmkywbxbxfal`.

## 1. Portée et activation
L'ERP-061 a mis en évidence l'absence de circuit `demande d'achat → approbation → commande fournisseur`. ERP-062 fournit **le schéma SQL, une RPC atomique, un service Python, un écran Streamlit et des tests**, préparés sans déployer le nouveau schéma sur la base principale.

**STATUT : NON ACTIF.** La migration `sql/ERP_062_PREPARATION_demandes_achats_20261123.sql` n'a été exécutée que dans `BEGIN … ROLLBACK`. Les nouvelles tables/RPC n'existent donc PAS durablement sur Supabase principal. Le panneau n'est pas visible sans `ERP_PURCHASE_REQUESTS_ENABLED=1`. Ne pas activer ce flag avant migration homologuée, deuxième acteur humain habilité et réception E2E.

## 2. Parcours implémenté
1. **CREATE** : document `DA-uuid`, motivation obligatoire (10–1 500 caractères), date de besoin ISO, 1 à 100 lignes avec matières actives et unités de stock figées, quantités positives, unicité du MP ; statut `BROUILLON`.
2. **SUBMIT** : seul le demandeur soumet son brouillon ; statut `SOUMISE`.
3. **APPROVE / REJECT** : approbateur actif et habilité **distinct du demandeur**, refus motivé (10–1 000 caractères), statut `APPROUVEE` / `REFUSEE` ; aucune auto-approbation.
4. **CONVERT** : une demande `APPROUVEE` uniquement est convertie en une commande fournisseur avec un fournisseur **actif**, prix unitaire saisi, quantités et références **strictement identiques à celles approuvées**. Conversion et création BC avec `erp_create_purchase_order` dans la **même transaction PostgreSQL**, lien unique `demande_id → commande_achat_id` et état `COMMANDEE`.
5. **Après BC** : le module Achats existant conserve les réceptions partielles/totales, le calcul du PMP, les lots, et le PDF de consultation du bon de commande ; la DA elle-même ne produit aucun mouvement, écriture SCF, paiement ni émission fournisseur.

**Piste d'audit / reprise** : une table d'opérations `erp_purchase_request_operations` verrouillée, clé `operation_id` unique, résultat idempotent et rejet d'une charge différente sous le même identifiant ; une table d'événements `erp_purchase_request_events` trace l'acteur, l'ancien/nouveau statut et l'opération. Les tables nouvelles sont RLS, sans accès anon/authenticated, et la RPC est `SECURITY INVOKER` accordée à `service_role` seulement. Le service vérifie l'utilisateur de session et le droit Achats **à chaque action**.

## 3. Preuves réelles SQL, toutes annulées
Sous une seule transaction par scénario dans le Supabase principal :
- DA avec 10 kg `DEMO26_MP1`, soumission, **deuxième approbateur TEMPORAIRE NON CONNECTABLE** créé uniquement dans la transaction annulée, conversion en BC 1 000 DZD, réception conforme 10 kg ; PMP/stock et rattachement BC vérifiés.
- Rejeu idempotent de la création de DA et de la conversion en BC ; aucun doublon.
- Refus : approbation prématurée, auto-approbation, quantité augmentée de 10 à 11 lors de conversion.
- Refus : matière inactive, MP dupliquée, même clé d'opération avec charge différente, rejet sans motif, approbation après rejet.
- Refus : fournisseur inactif ; conversion positive de **deux articles** `DEMO26_MP1` (10×100) et `DEMO26_MP2` (2×150), montant BC 1 300 DZD, couverture des deux lignes et absence de surachat.
- Test ACL RPC : `anon` et `authenticated` sans `EXECUTE` ; `service_role` autorisé, RLS active.

À la fin : **0 utilisateur temporaire, 0 table/DA/BC/BR et 0 mouvement de test persistés** ; quantité réelle `DEMO26_MP1` restaurée à 1 000 kg. Les identifiants de test `E2E62-` n'ont pas été laissés en base.

## 4. Fichiers ajoutés/modifiés
- `sql/ERP_062_PREPARATION_demandes_achats_20261123.sql` — DDL/RPC additive à homologuer, non appliquée.
- `modules/achats/requisitions.py` — service server-role, droits frais, validations et registre borné (refus si plus de 200 demandes plutôt que tronquer silencieusement).
- `modules/achats/requisitions_views.py` — écran DA avec soumission, décision, conversion DZD et reprise d'opération.
- `modules/achats/views.py` — ajout de `📝 Demandes d'achat` **uniquement si flag activé** ; dans ce mode, le formulaire legacy `Nouvelle Commande` est masqué au profit du circuit approuvé.
- `tests/test_erp062_purchase_requests.py` — validation, duplications, RBAC, erreur réseau et même identifiant d'opération, flag UI.
- `docs/ERP_062_DEMANDES_ACHAT_APPROBATION_20261123.md` (ce document), `docs/ETAT_AVANCEMENT.md`.

## 5. Risques et critères de levée
- Un seul utilisateur ERP réellement actif `ADMIN` en production. **Il est impossible d'approuver légitimement une DA de ce demandeur sans deuxième véritable utilisateur habilité.** Ne créer ni utilisateur fictif ni auto-approbation.
- Le flag masque le formulaire de création BC historique, **mais la RPC legacy `erp_create_purchase_order` reste techniquement appelable par le serveur**. Une obligation d'approbation globale sur tous les nouveaux BC nécessite une migration de bascule et une revue des flux hérités ; ce n'est pas encore une politique universelle en base.
- Le PDF BC reste `COPIE DE CONSULTATION - NON SIGNÉE / NON ÉMISE` ; émission, approbation budgétaire/seuils, signature, transmission au fournisseur et dossier de preuve restent à développer.
- La facture fournisseur, le rapprochement 3 voies BC/BR/facture et le paiement ne sont **pas inclus dans ERP-062**. Le bug Finance de lettrage #85 est préparé mais **non appliqué** ; homologation financière nécessaire avant toute activation.
- Streamlit Community Cloud non attesté à jour : issue [#78](https://github.com/Verwolfy/erp-mortier/issues/78). Aucune connexion navigateur ni TinyFish durant cette phase.
- Faire tester par deux utilisateurs humains habilités et sur une base TEST isolée avant autoriser les vrais ordres fournisseurs.

Suivi fonctionnel [#86](https://github.com/Verwolfy/erp-mortier/issues/86) ; blocage financier [#85](https://github.com/Verwolfy/erp-mortier/issues/85).

## 6. Suite
1. Vérifier CI GitHub sur le **SHA final** du présent lot, ne pas reprendre une exécution annulée.
2. Faire approuver l'installation de la migration DAO additive et le processus de création du deuxième approbateur.
3. Vérifier le déploiement Streamlit et les PDF réellement imprimés.
4. Concevoir l'émission du BC, la validation facture, le contrôle 3 voies et l'autorisation des paiements.
5. Préserver la séparation des tâches et l'absence de fausse écriture fiscale/SCF.
