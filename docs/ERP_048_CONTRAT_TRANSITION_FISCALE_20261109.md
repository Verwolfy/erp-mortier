# ERP-048 — Contrat de transition fiscale transactionnelle (préparation)

Date : 2026-11-09. Statut : CONCEPTION / NON DÉPLOYÉ. Branche : main.
Ce document ne modifie ni les taux ni les factures, et n'autorise aucune émission de facture fiscale modernisée.

## Constats vérifiés sur la principale
Projet Supabase : wenydirqtmkywbxbxfal. Projet TEST ffuhbmcfyexsbjwhryvj : INACTIVE, ne pas réactiver.
37 migrations enregistrées, dernière ERP-047 (20261109145442).
Requête en lecture seule du 2026-11-09 : 145 SKU actifs, 0 fiche de fiscalité VALIDEE, 0 SKU PRET_TECHNIQUEMENT, 4 lignes de facture existantes.
Code main consulté : modules/ventes/service.py calcule encore avec TAUX_TVA=0.19, TAUX_TIMBRE=0.01, MAX_TIMBRE=2500 et transmet ses totaux à erp_sale_transaction.
La simulation isolée modules/ventes/fiscal_repartition.py ventile les remises au centime ; elle ne remplace pas une transaction atomique.

## Invariants du futur moteur (critères bloquants)
1. La base calcule exclusivement avec la date juridique de l'opération et les paramètres réglementaires validés à cette date. Aucun taux ou seuil de secours dans Python ou SQL.
2. Pour chaque SKU, exiger une classification applicable et VALIDEE, source juridique, vérificateur, dates d'effet ; en l'absence de preuve, refuser explicitement plutôt que supposer NORMAL.
3. Gérer les régimes EXONERE et HORS_CHAMP par des flux dédiés documentés et validés ; ne pas les traiter implicitement comme taux zéro.
4. Ventiler les remises de ligne et globales au centime, vérifier l'égalité des assiettes et totals, contrôler la précision numérique ; arrondis déterministes.
5. Calculer côté serveur les preuves de chaque ligne puis remplir atomiquement les 12 champs ajoutés par ERP-046 ; ne pas accepter des taux ou preuves déclarés par le navigateur comme vérité.
6. Conserver la sémantique de DRAFT, VALIDATE, CANCEL, SHIP, les droits serveur, la correspondance avec la commande, l'idempotence operation_id et l'absence de sortie de stock avant BL.
7. Les avoirs se réfèrent à leur facture d'origine et à sa preuve fiscale ; pas de recalcul silencieux au taux du jour.
8. Timbre sur quittance / encaissements à traiter séparément selon la règle juridique datée et vérifiée ; aucun seuil supposé.
9. Ne jamais modifier ou régénérer les quatre lignes de facture historiques en l'absence de source fiscale fiable.
10. Ne pas élargir les GRANT/RLS ni utiliser SECURITY DEFINER pour contourner les accès.
11. Test PostgreSQL 17 jetable, scénarios négatifs, concurrentiels, de reprise et de droits ; CI complète verte avant migration sur principale.
12. Passage vers la nouvelle RPC via activation explicite, après validation juridique et recette authentifiée ; pas de bascule automatique du moteur actif.

## Ordre d'implémentation recommandé
A. Inventorier la définition effective de public.erp_sale_transaction et les contraintes de factures/lignes_facture ; documenter les états et chemins d'écriture.
B. Ajouter des tests contractuels de refus (SKU non validé, règle absente, taux ambigu, retour RPC incohérent, transaction rejouée, double requête concurrente).
C. Préparer une RPC parallèle compatible, sans remplacer la RPC actuelle ; ne pas créer de données fiscales réelles sans prérequis.
D. Vérifier les preuves ERP-046, la sécurité SQL, les calculs et l'historique dans une base PostgreSQL 17 éphémère GitHub Actions.
E. Faire valider les classifications SKU et paramètres réglementaires avec pièces officielles par les responsables habilités, puis seulement évaluer la bascule contrôlée.

## Points d'arrêt
Toute modification de droits SQL (RLS/GRANT), remplacement destructif de RPC, changement de taux réglementaire à fort impact, écriture non réversible ou activation transactionnelle nécessite validation distincte.
Aucune qualification juridique ou comptable ne peut être inventée.

## Reprise de prochaine session
Vérifier le SHA de main et sa CI après ce commit ; lire docs/ETAT_AVANCEMENT.md puis ce fichier. Contrôler le schéma et la fonction erp_sale_transaction en lecture seule. Ne jamais réactiver Supabase TEST. Conserver le moteur existant jusqu'à résolution des prérequis.
