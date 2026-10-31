# Sofiane ERP — reprise optimisation après validation Streamlit (31 octobre 2026)

## Décision utilisateur
- Conserver **erp-mortier-test** (projet `ffuhbmcfyexsbjwhryvj`) en pause : **ne pas supprimer, ne pas réactiver, ne pas modifier**.
- Continuer les optimisations sur GitHub `Verwolfy/erp-mortier` branche `main` et Supabase PRODUCTION `wenydirqtmkywbxbxfal`, sans générer de données réglementaires fictives.

## Progrès vérifiés
- Capture utilisateur : connexion réussie à `https://nextgent-erp.streamlit.app/` comme **Administrateur Principal / ADMIN**, écran Administration & Référentiels fonctionnel, 7 clients visibles, menus de navigation chargés.
- Le correctif de diagnostic d'authentification est publié sur `main` (commit `c6de28d0bd8bccc818ee1b5d67543bf26ea8caa4`). Les deux workflows GitHub de ce commit (`audit de reconciliation sans modification`, `tests lot C facturation`) sont `completed/success`.
- Supabase : PRODUCTION `ACTIVE_HEALTHY` ; TEST `INACTIVE` et conservé.
- Migrations 012–032 (21 versions) déjà enregistrées dans l'historique Supabase. Registre applicatif `public.schema_migrations` historiquement vide ; aucun rejeu automatique.
- Le déclencheur fiscal 032 existe et est activé ; le brouillon `sql/013_facturation_parametree.sql` n'est pas appliqué.
- L'authentification fonctionnelle ne démontre ni la conformité fiscale ni le bon fonctionnement de chaque module.

## Risques et contrôles à poursuivre
1. **Sécurité urgente :** le mot de passe temporaire administrateur a été montré en clair dans une capture. Le remplacer par un secret fort hors conversation et éviter son inclusion dans les journaux SQL.
2. **Tests Streamlit en lecture seule :** Administration → Qualification TVA SKU (7 SKU, classification fiscale toujours absente avant validation) ; Ventes ; Stocks ; Finance/SCF ; RH. Consigner tout écran et erreur, sans création de pièces comptables ou fiscales.
3. **Réconciliation :** comparer les scripts SQL avec le schéma réel et les 21 migrations, ne pas inventer d'empreintes dans `schema_migrations`.
4. **Facturation réglementaire :** ne pas appliquer le brouillon 013 ni les scripts `supabase_pending` modifiant `GRANT/REVOKE` avant vérifications de sécurité et de règles officielles.
5. **Guide et aide :** mettre à jour les procédures de déploiement et la distinction entre CI verte, application accessible et modules réellement homologués.

## État
**EN COURS** : authentification Streamlit et écran Administration visibles ; ensemble des tests fonctionnels non terminé. Aucun changement SQL ou permissions lors de ce point de reprise.
