# NEXTGEN ERP — Reprise sécurité QR / intégrité des brouillons — 2026-11-04

## Résultat
- Branche : `Verwolfy/erp-mortier/main`.
- Registre QR 033 **non appliqué**. Schéma `erp_private` existant confirmé dans Supabase PRODUCTION `wenydirqtmkywbxbxfal`.
- Vérification SQL lecture seule : `schema_prive_existe=true`, `aucune_table_qr_exposee=true`, `registre_deja_present=false`, `evenements_deja_presents=false`. Aucune modification en production.
- Préparation SQL : `sql/033_document_trace_registry_PREPARATION.sql`, non exécuté, avec RLS/FORCE RLS, aucune politique permissive ni grant API ; `sql/033_preflight_document_trace_READONLY.sql`, pour préflight sans modification.
- Empreinte SHA-256 reproductible : `modules/documents/trace_integrity.py`; canonicalisation stable des champs contractuels, ordre des lignes préservé, contrôle ID/date/statut BROUILLON, contrôle des montants par normalisation financière. Ceci n'est PAS une signature ni une preuve d'émission.
- UI : affichage de l'empreinte locale sous le QR dans `modules/documents/views.py`, explicitement non certifiée. Aucun stockage durable ; elle change avec le contenu.
- Tests : `tests/test_document_tracking_integrity.py` (stabilité, changements de tiers/prix/ordre, refus des données invalides, absence de champs hors contrat), `tests/test_document_tracking_sql.py` (registre privé et absent de grants) ; test UI ajout.
- Commits : `3f9b24d` (empreinte), `f7c18b1` (tests), `26cc68e` (preflight), `aa9d0a4` (UI), `e493832` (test UI).

## Points bloquants avant application de la migration 033
1. Définir le modèle d'identité autoritative côté serveur, car les utilisateurs ERP Streamlit sont distincts de `auth.users`.
2. Définir les droits de création/validation/annulation, journal append-only, concurrence, mise à jour et versioning ; le champ `version_no` actuel ne constitue pas à lui seul un historisation multiversion.
3. Définir politiques RLS et RPC serveur avec tests d'accès inter-rôles et d'étanchéité des informations.
4. Définir rétention, audit, conservation des brouillons et mécanismes de vérification publique sans révéler de données personnelles.
5. Obtenir approbation explicite avant création de tables/GRANT/RLS sur production et vérifier le comportement sur environnement isolé.

## Suite
- Lire les résultats CI des workflows du commit le plus récent `e493832` ; corriger les régressions.
- Sur Streamlit, vérifier empreinte et exports (Devis, Facture brouillon, BL, Bon de consommation) avec données de test fictives.
- Ne pas présenter un QR local non enregistré comme preuve d'authenticité.
- Aucun taux fiscal inventé, aucune émission officielle, aucune écriture de production effectuée dans cette intervention.
