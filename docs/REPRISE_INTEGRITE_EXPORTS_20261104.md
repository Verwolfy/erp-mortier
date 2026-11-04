# NEXTGEN ERP — Reprise optimisation documentaire — 4 novembre 2026

## Contexte et décisions
- GitHub : `Verwolfy/erp-mortier`, branche `main`, Streamlit : `https://nextgent-erp.streamlit.app/`.
- Supabase PRODUCTION : `wenydirqtmkywbxbxfal`. Projet TEST conservé en pause ; ne pas supprimer ni réactiver.
- Tous les documents générés restent des **brouillons non émis**.
- Logo source HD officiel : `assets/nextgen_logo_hd.jpg` et en-tête/pied générés dans `modules/documents/branding_images.py`.
- 20 modèles dans `modules/documents/views.py` et `layout_nextgen.py`. Édition de lignes via champs Streamlit sans `st.data_editor`.
- Aucune règle fiscale inventée : les taxes sont saisies séparément, aucune émission officielle.

## Travaux réalisés dans ce lot
- Défaut découvert : les fonctions d'export PDF/Word pouvaient imprimer des totaux incohérents si appelées directement avec un brouillon externe/ancien.
- `modules/documents/calculations.py` : nouvelle normalisation `normalize_financial_export`, sans mutation de l'entrée. Chiffres dérivés des quantités et prix par Decimal. Montants de ligne/HT/TTC déclarés contradictoires refusés. Modèles vierges et non chiffrés préservés.
- Vérification des produits quantity×price contre la limite avant arrondi (évite erreurs Decimal involontaires et dépassements).
- `modules/documents/views.py` : normalisation utilisée avant chaque export PDF ou DOCX.
- `tests/test_documents_nextgen.py` : nouveau scénario de calcul automatique en export, incohérence de ligne ou TTC, modèles sans prix, montants excessifs, absence de mutation de l'objet.
- Commits code : `dcb4be63`, `5ff27830`, `b226d836`.
- À la dernière lecture : tests ERP du commit `b226d836` réussis (GitHub Actions run `41836599108`). Audit réconciliation du même commit `41836599099` en cours.
- Aucun SQL, aucun GRANT/RLS ni changement aux secrets effectués.

## Suite recommandée — opérations restantes
1. Vérifier le résultat de l'audit CI final et corriger toute anomalie réelle.
2. Vérifier visuellement dans Streamlit des PDF/DOCX issus de Facture, Devis, BL, Bon de consommation avec en-tête/pied officiels et QR.
3. Concevoir préremplissage des brouillons depuis les référentiels Clients/SKU de Supabase **en lecture seule**, après contrôle des colonnes réelles et des droits.
4. Conception du registre de traçabilité QR (identifiant, version, états et contrôles d'accès) : migration additive versionnée à tester avant déploiement, jamais une validation fictive.
5. Validation juridique/comptable algérienne obligatoire avant émission définitive des factures/avoirs.
6. Exécuter les tests de régression, actualiser les guides et constater le déploiement Streamlit.

## Risques
- Les calculateurs ne déterminent aucune taxe officielle ni le droit au timbre.
- Une page Streamlit accessible ne prouve pas une homologation fiscale.
- Le QR actuel est un identifiant local non certifié, sans registre public.
