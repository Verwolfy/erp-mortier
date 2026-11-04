# NEXTGEN ERP — Reprise du projet QR — 4 novembre 2026

## Actions réalisées
- GitHub `Verwolfy/erp-mortier`, branche `main`. Dernier lot : `sql/033_document_trace_registry_PREPARATION.sql` (commit `90af307`) et `tests/test_document_tracking_sql.py` (commit `34e3a27`).
- Schéma Supabase PRODUCTION `erp_private` confirmé existant par requête SQL en lecture seule.
- Aucune table de documents ou QR préexistante identifiée dans les schémas interrogés (`public`, `private`, `internal`), vérification ciblée.
- Projet de registre privé de QR : identifiant `NG-<32 hex>`, document/type/référence/version/état, empreinte SHA-256, auteur, dates, événement/action/acteur et métadonnées bornées.
- Activation RLS + FORCE RLS, aucun GRANT ni POLICY permissive, révocation de tous les accès Data API. Aucun `SECURITY DEFINER` ; pas d'endpoint ni de suivi public fictif.
- Test de structure statique ajouté, CI GitHub lancée.
- Aucune commande DDL exécutée sur Supabase PRODUCTION ; projet TEST `ffuhbmcfyexsbjwhryvj` toujours en pause.

## Contexte
- Les 20 modèles de documents ont déjà PDF/Word/JSON, QR local unique et import JSON, préremplissage des tiers, SKU et MP avec permission de lecture serveur.
- Les exports sont des BROUILLONS non émis ; aucune TVA supposée ni facture officielle validée.
- Référentiels PROD en lecture : 7 clients, 6 fournisseurs, 149 SKU, 56 produits, 120 MP.

## Suite impérative
1. Vérifier les workflows `41864219332` (tests ERP), `41864219308` (audit) de `34e3a27`; corriger les échecs éventuels.
2. Déterminer identité ERP vérifiée, parcours de validation et autorisation du futur RPC d'écriture, politique d'accès aux données et rétention ; tests de sécurité RLS nécessaires.
3. Ne pas appliquer `033_document_trace_registry_PREPARATION.sql` à la production avant revue de sécurité et approbation pour ce changement critique.
4. Quand prêt : essai sur environnement isolé (sans réactiver la base TEST sans accord), migration versionnée, tests SQL et de concurrence, contrôle du QR et audits.
5. Vérification visuelle Streamlit des documents et exports réels, sans émission fiscale.

## Particularité
La migration SQL est **une proposition non appliquée**, pas une mise en production. Elle crée volontairement un registre inaccessible par les clients API tant que l'authentification métier et les politiques n'ont pas été homologuées.
