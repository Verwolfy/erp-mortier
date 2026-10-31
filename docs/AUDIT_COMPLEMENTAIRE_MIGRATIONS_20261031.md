# Audit complémentaire des migrations — 31 octobre 2026

Cible : Supabase PRODUCTION `wenydirqtmkywbxbxfal`, dépôt `Verwolfy/erp-mortier` branche `main`.

## Preuves SQL en lecture seule
- Historique Supabase : 21 migrations numérotées 012–032 déjà enregistrées.
- `public.schema_migrations` : 0 ligne.
- Fonction `public.erp_facture_parametre(text,date,text)` : absente.
- Fonction `public.erp_exoneration_tva_precontrole_vente(text,text[],date)` : présente.
- Tables `scf_plan_comptes`, `paie_bulletins_v2`, `erp_sku_fiscalite`, `erp_exonerations_tva_clients` : présentes.
- Déclencheur `erp_factures_garde_exonerations` sur `public.factures` : actif (`tgenabled='O'`).

## Décision
Aucune migration à rejouer dans la série 012–032. Le script `sql/013_facturation_parametree.sql` est explicitement un brouillon et modifie des fonctions fiscales, ainsi que les privilèges SQL : ne pas appliquer sans revue métier et de sécurité. La présence d'objets ne prouve pas la parité complète du schéma. Ne pas enregistrer des empreintes SHA-256 supposées dans `schema_migrations`.

## Suite
Établir la matrice exacte fichiers ↔ migrations ↔ objets ; vérifier la fonction transactionnelle, les paramètres fiscaux applicables et les autorisations avant une éventuelle migration nouvelle. Contrôler en parallèle les journaux Streamlit, car l'écran de connexion affiche une indisponibilité technique. Aucun changement de données, de RLS ou de GRANT pendant cet audit.
